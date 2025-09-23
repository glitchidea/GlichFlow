from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.core.serializers.json import DjangoJSONEncoder
import json

from accounts.models import CustomUser
from .models import PackageGroup, Package, ExtraService, PackageFeature
from .forms import PackageGroupForm, PackageForm, ExtraServiceForm, PackageFeatureForm


def _user_is_accountant(user: CustomUser) -> bool:
    return getattr(user, 'has_tag', lambda t: False)('muhasebeci') or getattr(user, 'has_tag', lambda t: False)('muhasebeadmin')


def _user_is_accounting_admin(user: CustomUser) -> bool:
    return getattr(user, 'has_tag', lambda t: False)('muhasebeadmin')


@login_required
def index(request: HttpRequest) -> HttpResponse:
    if not _user_is_accountant(request.user):
        return HttpResponseForbidden('Bu sayfaya erişim için muhasebe etiketi gerekir.')

    groups = PackageGroup.objects.prefetch_related('packages', 'packages__features').all()
    extra_services = ExtraService.objects.filter(is_active=True)
    features = PackageFeature.objects.select_related('package', 'package__group').all()
    
    # JSON verilerini hazırla
    groups_data = []
    for group in groups:
        group_data = {
            'id': group.id,
            'name': group.name,
            'description': group.description or '',
            'packages': []
        }
        for package in group.packages.all():
            package_data = {
                'id': package.id,
                'name': package.name,
                'base_price': float(package.base_price),
                'extra_pages_multiplier': float(package.extra_pages_multiplier),
                'features': []
            }
            for feature in package.features.all():
                package_data['features'].append({
                    'id': feature.id,
                    'text': feature.text
                })
            group_data['packages'].append(package_data)
        groups_data.append(group_data)
    
    extra_services_data = []
    for extra in extra_services:
        extra_data = {
            'id': extra.id,
            'name': extra.name,
            'description': extra.description or '',
            'pricing_type': extra.pricing_type,
            'price': float(extra.price),
            'percentage': float(extra.percentage),
            'input_type': extra.input_type,
            'unit_label': extra.unit_label or '',
            'min_quantity': extra.min_quantity,
            'max_quantity': extra.max_quantity,
            'default_quantity': extra.default_quantity,
            'options': extra.options,
            'is_required': extra.is_required,
            'is_checkbox': extra.input_type == 'checkbox',
            'group_id': extra.group.id if extra.group else None
        }
        extra_services_data.append(extra_data)
    
    context = {
        'groups': groups,
        'groups_json': json.dumps(groups_data, cls=DjangoJSONEncoder),
        'extra_services': extra_services,
        'extra_services_json': json.dumps(extra_services_data, cls=DjangoJSONEncoder),
        'is_admin': _user_is_accounting_admin(request.user),
        'features': features,
    }
    return render(request, 'accounting/index.html', context)


@login_required
def package_manager(request: HttpRequest) -> HttpResponse:
    if not _user_is_accounting_admin(request.user):
        return HttpResponseForbidden('Bu sayfaya erişim için muhasebeadmin etiketi gerekir.')

    groups = PackageGroup.objects.all()
    packages = Package.objects.select_related('group').all()
    extra_services = ExtraService.objects.select_related('group').all()
    features = PackageFeature.objects.select_related('package', 'package__group').all()
    context = {
        'groups': groups,
        'packages': packages,
        'extra_services': extra_services,
        'features': features,
    }
    return render(request, 'accounting/package_manager.html', context)


# ---- CRUD for muhasebeadmin ----

@login_required
def group_create(request: HttpRequest) -> HttpResponse:
    if not _user_is_accounting_admin(request.user):
        return HttpResponseForbidden('Bu işlem için muhasebeadmin etiketi gerekir.')
    if request.method == 'POST':
        form = PackageGroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.created_by = request.user
            group.save()
            return redirect('accounting:package_manager')
    else:
        form = PackageGroupForm()
    return render(request, 'accounting/crud/group_form.html', {'form': form})


@login_required
def group_update(request: HttpRequest, pk: int) -> HttpResponse:
    if not _user_is_accounting_admin(request.user):
        return HttpResponseForbidden('Bu işlem için muhasebeadmin etiketi gerekir.')
    group = get_object_or_404(PackageGroup, pk=pk)
    if request.method == 'POST':
        form = PackageGroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            return redirect('accounting:package_manager')
    else:
        form = PackageGroupForm(instance=group)
    return render(request, 'accounting/crud/group_form.html', {'form': form, 'object': group})


@login_required
def group_delete(request: HttpRequest, pk: int) -> HttpResponse:
    if not _user_is_accounting_admin(request.user):
        return HttpResponseForbidden('Bu işlem için muhasebeadmin etiketi gerekir.')
    group = get_object_or_404(PackageGroup, pk=pk)
    if request.method == 'POST':
        group.delete()
        return redirect('accounting:package_manager')
    return render(request, 'accounting/crud/confirm_delete.html', {'object': group, 'type': 'Paket Grubu'})


@login_required
def package_create(request: HttpRequest) -> HttpResponse:
    if not _user_is_accounting_admin(request.user):
        return HttpResponseForbidden('Bu işlem için muhasebeadmin etiketi gerekir.')
    if request.method == 'POST':
        form = PackageForm(request.POST)
        if form.is_valid():
            package = form.save(commit=False)
            package.created_by = request.user
            package.save()
            return redirect('accounting:package_manager')
    else:
        form = PackageForm()
    return render(request, 'accounting/crud/package_form.html', {'form': form})


@login_required
def package_update(request: HttpRequest, pk: int) -> HttpResponse:
    if not _user_is_accounting_admin(request.user):
        return HttpResponseForbidden('Bu işlem için muhasebeadmin etiketi gerekir.')
    package = get_object_or_404(Package, pk=pk)
    if request.method == 'POST':
        form = PackageForm(request.POST, instance=package)
        if form.is_valid():
            form.save()
            return redirect('accounting:package_manager')
    else:
        form = PackageForm(instance=package)
    return render(request, 'accounting/crud/package_form.html', {'form': form, 'object': package})


@login_required
def package_delete(request: HttpRequest, pk: int) -> HttpResponse:
    if not _user_is_accounting_admin(request.user):
        return HttpResponseForbidden('Bu işlem için muhasebeadmin etiketi gerekir.')
    package = get_object_or_404(Package, pk=pk)
    if request.method == 'POST':
        package.delete()
        return redirect('accounting:package_manager')
    return render(request, 'accounting/crud/confirm_delete.html', {'object': package, 'type': 'Paket'})


@login_required
def extra_create(request: HttpRequest) -> HttpResponse:
    if not _user_is_accounting_admin(request.user):
        return HttpResponseForbidden('Bu işlem için muhasebeadmin etiketi gerekir.')
    if request.method == 'POST':
        form = ExtraServiceForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('accounting:package_manager')
    else:
        form = ExtraServiceForm()
    return render(request, 'accounting/crud/extra_form.html', {'form': form})


@login_required
def extra_update(request: HttpRequest, pk: int) -> HttpResponse:
    if not _user_is_accounting_admin(request.user):
        return HttpResponseForbidden('Bu işlem için muhasebeadmin etiketi gerekir.')
    extra = get_object_or_404(ExtraService, pk=pk)
    if request.method == 'POST':
        form = ExtraServiceForm(request.POST, instance=extra)
        if form.is_valid():
            form.save()
            return redirect('accounting:package_manager')
    else:
        form = ExtraServiceForm(instance=extra)
    return render(request, 'accounting/crud/extra_form.html', {'form': form, 'object': extra})


@login_required
def extra_delete(request: HttpRequest, pk: int) -> HttpResponse:
    if not _user_is_accounting_admin(request.user):
        return HttpResponseForbidden('Bu işlem için muhasebeadmin etiketi gerekir.')
    extra = get_object_or_404(ExtraService, pk=pk)
    if request.method == 'POST':
        extra.delete()
        return redirect('accounting:package_manager')
    return render(request, 'accounting/crud/confirm_delete.html', {'object': extra, 'type': 'Ek Hizmet'})


@login_required
def feature_create(request: HttpRequest) -> HttpResponse:
    if not _user_is_accounting_admin(request.user):
        return HttpResponseForbidden('Bu işlem için muhasebeadmin etiketi gerekir.')
    if request.method == 'POST':
        form = PackageFeatureForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('accounting:package_manager')
    else:
        form = PackageFeatureForm()
    return render(request, 'accounting/crud/feature_form.html', {'form': form})


@login_required
def feature_update(request: HttpRequest, pk: int) -> HttpResponse:
    if not _user_is_accounting_admin(request.user):
        return HttpResponseForbidden('Bu işlem için muhasebeadmin etiketi gerekir.')
    feature = get_object_or_404(PackageFeature, pk=pk)
    if request.method == 'POST':
        form = PackageFeatureForm(request.POST, instance=feature)
        if form.is_valid():
            form.save()
            return redirect('accounting:package_manager')
    else:
        form = PackageFeatureForm(instance=feature)
    return render(request, 'accounting/crud/feature_form.html', {'form': form, 'object': feature})


@login_required
def feature_delete(request: HttpRequest, pk: int) -> HttpResponse:
    if not _user_is_accounting_admin(request.user):
        return HttpResponseForbidden('Bu işlem için muhasebeadmin etiketi gerekir.')
    feature = get_object_or_404(PackageFeature, pk=pk)
    if request.method == 'POST':
        feature.delete()
        return redirect('accounting:package_manager')
    return render(request, 'accounting/crud/confirm_delete.html', {'object': feature, 'type': 'Paket Özelliği'})


