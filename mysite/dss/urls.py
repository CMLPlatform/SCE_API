from django.urls import path
from .views import ExperimentComparisonInitView, McdaWizardView, ExperimentResultsView

urlpatterns = [
    path("experiments/", ExperimentComparisonInitView.as_view(), name="experiment-init"),
    path("<int:session_id>/step/<int:step>/", McdaWizardView.as_view(), name="wizard"),
    path("results/<int:session_id>/", ExperimentResultsView.as_view(), name="results"),
]
