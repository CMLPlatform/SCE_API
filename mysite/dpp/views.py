from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse
from .models import ProductionLine
from api.serializers import ProductionLineSerializer

def start(request):
    return HttpResponse("Welcome to the Lasers4MaaS project.")


def production_line_create(request):
    if request.method == "POST":
        serializer = ProductionLineSerializer(data=request.POST)
        if serializer.is_valid():
            production_line = serializer.save()
            messages.success(request, "Production line created successfully!")
            return redirect("factory:production_line_edit", pk=production_line.pk)
        else:
            # HTMX will re-render the form with errors
            return render(request, "factory/production_line_form.html", {
                "form_data": request.POST,
                "errors": serializer.errors,
            })

    return render(request, "factory/production_line_form.html")


# This view will be used later when we add related objects
def production_line_edit(request, pk):
    line = ProductionLine.objects.get(pk=pk)
    return render(request, "factory/production_line_edit.html", {"line": line})

