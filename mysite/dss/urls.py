from django.urls import path
from django.views.generic.base import TemplateView
from .views import (
    ExperimentKpiView, WeldStationKpiView,
    ExperimentComparisonInitView, KamComparisonInitView,
    McdaCalculationView, McdaWizardView, McdaResultsView, plot_view
)

urlpatterns = [
    path("kam-input/", TemplateView.as_view(template_name="dss/kam_input.html"), name="kam-input"),
    path("experiment/", ExperimentKpiView.as_view(), name="experiment"),
    path("welding-station/", WeldStationKpiView.as_view(), name="weld-station"),
    path("experiments/", ExperimentComparisonInitView.as_view(), name="pd-init"),
    path("welding-stations/", KamComparisonInitView.as_view(), name="kam-init"),
    path("calculate/", McdaCalculationView.as_view(), name="mcda"),
    path("<uuid:token>/step/<int:step>/", McdaWizardView.as_view(), name="wizard"),
    path("results/<uuid:token>/", McdaResultsView.as_view(), name="results"),
    path("mcda/<uuid:token>/plot/<str:plot_name>/", plot_view, name="mcda-plot"),
]
