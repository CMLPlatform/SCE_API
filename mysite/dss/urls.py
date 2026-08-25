from django.urls import path
from .views import (
    ExperimentComparisonInitView, KamComparisonInitView,
    McdaWizardView, McdaResultsView, plot_view
)

urlpatterns = [
    path("experiments/", ExperimentComparisonInitView.as_view(), name="pd-init"),
    path("welding-stations/", KamComparisonInitView.as_view(), name="kam-init"),
    path("<int:session_id>/step/<int:step>/", McdaWizardView.as_view(), name="wizard"),
    path("results/<int:pk>/", McdaResultsView.as_view(), name="results"),
    path("mcda/<int:session_id>/plot/<str:plot_name>/", plot_view, name="mcda-plot"),
]
