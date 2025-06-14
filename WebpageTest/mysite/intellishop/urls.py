# URL patterns that map URLs to view functions within the IntelliShop app
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),  # Root route to index
    path('home/', views.index_home, name='index_home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register, name='register'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('base/', views.template, name='template'),
    path('coupon_for_aliexpress/', views.aliexpress_coupons, name='aliexpress_coupons'),
    path('coupon/<str:store>/', views.coupon_detail, name='coupon_detail'),
    path('filter_search/', views.filter_search, name='filter_search'),
    path('profile/', views.profile_view, name='profile'),
    path('logout/', views.logout_view, name='logout'),
    path('coupon/<str:code>/', views.coupon_code_view, name='coupon_code'),
    path('favorites/', views.favorites_view, name='favorites'),
    path('show_all_discounts/', views.show_all_discounts, name='show_all_discounts'),
    # path('add_favorite/', views.add_favorite_view, name='add_favorite'),
    # path('remove_favorite/<int:coupon_id>/', views.remove_favorite, name='remove_favorite'),
] 

