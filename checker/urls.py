from django.urls import path

from checker import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("partners/", views.partners, name="partners"),
    path("partners/new/", views.partner_new, name="partner_new"),
    path("requirements/new/", views.requirement_edit, name="requirement_new"),
    path("requirements/<int:pk>/", views.requirement_detail, name="requirement_detail"),
    path("requirements/<int:pk>/edit/", views.requirement_edit, name="requirement_edit"),
    path("packages/new/", views.package_new, name="package_new"),
    path("packages/<int:pk>/", views.package_detail, name="package_detail"),
    path("packages/<int:pk>/upload/", views.asset_upload, name="asset_upload"),
    path("packages/<int:pk>/assets/<int:asset_id>/download/", views.asset_download, name="asset_download"),
    path("packages/<int:pk>/assets/<int:asset_id>/remove/", views.asset_remove, name="asset_remove"),
    path("packages/<int:pk>/reviews/<int:requirement_id>/", views.manual_review, name="manual_review"),
    path("audit/", views.audit_log, name="audit"),
    path("api/v1/packages/", views.api_packages, name="api_packages"),
    path("api/v1/packages/<int:pk>/report/", views.api_report, name="api_report"),
    path("health/", views.health, name="health"),
]
