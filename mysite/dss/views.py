import pandas as pd
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .serializers import McdaRequestSerializer, McdaResponseSerializer
from .mcda import mcda


class McdaCalculationView(APIView):
    def post(self, request):
        request_serializer = McdaRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        data = request_serializer.validated_data

        # Convert some raw data to read-to-use data types
        try:
            decision_matrix = pd.DataFrame(data["decision_matrix"])
        except BaseException as e:
            return Response({"Issue with decision matrix": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = mcda(
                df=decision_matrix,
                directions=data["directions"],
                scenario=data["scenario"],
                method=data["method"],
                weight_mode=data["weight_mode"],
                groups=data.get("groups"),
                group_weight=data.get("group_weights"),
                thresholds=data.get("thresholds"),

                # Veto settings
                veto_type=data["veto_type"],
                use_veto=(data["veto_type"]!="no"),
                veto_thresholds=data.get("veto_thresholds"),
                penalty_factor=data.get("penalty_factor"),

                # Weight structure settings (group-level and local)
                sampling_mode=data.get("sampling_mode"),
                group_lb=data.get("group_lb"),
                group_ub=data.get("group_ub"),
                group_order_constraints=data.get("group_order_constraints"),
                local_lb=data.get("local_lb"),
                local_ub=data.get("local_ub"),
                local_order_constraints=data.get("local_order_constraints"),
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        response_data = {
            "shape": data["shape"],
            "operation": data["operation"],
            "result": result,
        }
        response_serializer = McdaResponseSerializer(response_data)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
