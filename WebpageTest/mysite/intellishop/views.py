# View functions that handle HTTP requests and return responses
from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models.mongodb_models import User, Coupon
import json
from pymongo.errors import DuplicateKeyError
from bson.objectid import ObjectId
import csv
import os
from datetime import datetime
from django.templatetags.static import static

def index(request):
    return render(request, 'intellishop/index.html')

def index_home(request):
    # Get user details from session
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    
    # Get user from MongoDB
    user = User.find_one({'_id': ObjectId(user_id)})
    if not user:
        return redirect('login')

    # Get path to JSON file
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, 'intellishop', 'data', 'coupon_samples.json')
    
    # Add fallback path if the primary one doesn't exist
    if not os.path.exists(json_path):
        alt_json_path = os.path.join(base_dir, 'data', 'coupon_samples.json')
        if os.path.exists(alt_json_path):
            json_path = alt_json_path
    
    # Load ONLY the coupons from the JSON file
    formatted_coupons = []
    
    try:
        with open(json_path, 'r') as f:
            json_coupons = json.load(f)
            for coupon in json_coupons:
                # Get the product categories, or use a default if empty
                categories = coupon['product_categories']
                coupon_name = ' & '.join(categories).title() if categories else "All Products"
                
                # Format the amount based on discount_type
                amount = f"{coupon['amount']}%" if coupon['discount_type'] == 'percent' else f"${coupon['amount']}"
                
                formatted_coupon = {
                    'store_name': 'AliExpress',
                    'store_logo': '',  # Empty since we're not sure about the logo
                    'code': coupon['code'],
                    'amount': amount,
                    'name': coupon_name,
                    'description': coupon['description'],
                    'date_expires': datetime.strptime(coupon['date_expires'].split('T')[0], '%Y-%m-%d'),
                    'store_url': 'https://www.aliexpress.com',
                    'minimum_amount': coupon['minimum_amount']
                }
                formatted_coupons.append(formatted_coupon)
    except Exception as e:
        print(f"Error loading JSON coupons: {e}")

    context = {
        'user': {
            'email': user.get('email'),
            'status': user.get('status', []),
            'hobbies': user.get('hobbies', [])
        },
        'filtered_coupons': formatted_coupons
    }
    
    return render(request, 'intellishop/index_home_original.html', context)

def login_view(request):
    # If user is already logged in, redirect to home
    if request.session.get('user_id'):
        return redirect('index_home')
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print("\n=== FULL DEBUG ===")
            print("Attempting login with:", data)
            
            # Find user and print raw result
            collection = User.get_collection()
            raw_user = collection.find_one({'email': data['email']})
            print("Raw MongoDB result:", raw_user)
            
            user = User.find_one({'email': data['email']})
            print("User object:", user)
            
            print("=== Login Debug ===")
            print("1. Login attempt with email:", data['email'])
            print("2. Provided password:", data['password'])
            
            # Find user by email only first
            if user:
                print("4. User details:", {
                    'username': user.get('username'),
                    'email': user.get('email'),
                    'password': user.get('password'),
                    'status': user.get('status')
                })
                
                stored_password = user.get('password', '')
                input_password = data.get('password', '')
                print("5. Password comparison:")
                print(f"   - Stored password: '{stored_password}'")
                print(f"   - Input password: '{input_password}'")
                print(f"   - Length of stored password: {len(stored_password)}")
                print(f"   - Length of input password: {len(input_password)}")
                print(f"   - Are passwords equal? {stored_password == input_password}")
                
                if stored_password == input_password:
                    request.session['user_id'] = str(user['_id'])
                    request.session['username'] = user['username']
                    
                    # Debug session data
                    print("=== SESSION DEBUG ===")
                    print("Session ID:", request.session.session_key)
                    print("All session data:", dict(request.session))
                    
                    return JsonResponse({
                        'status': 'success',
                        'message': f"Welcome back {user['username']}",
                        'redirect': '/home/',
                        'user_id': str(user['_id'])
                    })
                else:
                    print("6. Password mismatch")
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Wrong Email/Password'
                    }, status=400)
            else:
                print("3. No user found with this email")
                return JsonResponse({
                    'status': 'error',
                    'message': 'Wrong Email/Password'
                }, status=400)
                
        except Exception as e:
            print("Login error:", str(e))
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
            
    return render(request, 'intellishop/login.html')

def register(request):
    # If user is already logged in, redirect to home
    if request.session.get('user_id'):
        return redirect('index_home')
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print("Registration data:", data)  # Debug log
            
            # Check if user already exists
            existing_user = User.get_by_username(data['username'])
            if existing_user is not None:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Username already exists'
                }, status=400)
            
            existing_email = User.get_by_email(data['email'])
            if existing_email is not None:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Email already exists'
                }, status=400)
            
            # Create new user in MongoDB
            user_id = User.create_user(
                username=data['username'],
                password=data['password'],
                email=data['email'],
                status=data['status'],
                age=data['age'],
                location=data['location'],
                hobbies=data['hobbies']
            )
            print("Created user with ID:", user_id)  # Debug log
            
            return JsonResponse({
                'status': 'success', 
                'message': 'User registered successfully',
                'user_id': str(user_id)
            })
            
        except Exception as e:
            print("Registration error:", str(e))  # Debug log
            return JsonResponse({
                'status': 'error', 
                'message': str(e)
            }, status=400)
    
    return render(request, 'intellishop/register.html')

def dashboard(request):
    try:
        # Get all users from MongoDB without any sorting
        users = list(User.find())  # Convert cursor to list immediately
        
        # Process the users
        users_list = []
        for user in users:
            if user is not None:
                # Convert ObjectId to string and ensure all fields exist
                user_data = {
                    'username': user.get('username', ''),
                    'email': user.get('email', ''),
                    'password': user.get('password', ''),
                    'status': user.get('status', ''),
                    'age': user.get('age', ''),
                    'location': user.get('location', ''),
                    'hobbies': user.get('hobbies', []),
                    '_id': str(user.get('_id', ''))
                }
                users_list.append(user_data)
        
        return render(request, 'intellishop/dashboard.html', {'users': users_list})
        
    except Exception as e:
        # Handle any errors and return an error message
        return render(request, 'intellishop/dashboard.html', {
            'users': [],
            'error': f"Error loading users: {str(e)}"
        })

def template(request):
    return render(request, 'intellishop/Site_template.html')

def aliexpress_coupons(request):
    code = request.GET.get('code')
    if code:
        # Get the specific coupon details from your JSON file
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        json_path = os.path.join(base_dir, 'intellishop', 'data', 'coupon_samples.json')
        
        # Add fallback path if the primary one doesn't exist
        if not os.path.exists(json_path):
            alt_json_path = os.path.join(base_dir, 'data', 'coupon_samples.json')
            if os.path.exists(alt_json_path):
                json_path = alt_json_path
        
        try:
            with open(json_path, 'r') as f:
                coupons = json.load(f)
                coupon = next((c for c in coupons if c['code'] == code), None)
                if coupon:
                    return render(request, 'intellishop/coupon_for_aliexpress.html', {'coupon': coupon})
        except Exception as e:
            print(f"Error loading coupon: {e}")
    
    return render(request, 'intellishop/coupon_for_aliexpress.html', {'error': 'Coupon not found'})

def coupon_detail(request, store):
    # Dictionary mapping store slugs to their display names
    store_names = {
        'lastprice': 'Lastprice / לאסט פרייס',
        'liberty': 'Liberty / ליברטי',
        'weshoes': 'Weshoes / ווישוז',
        'twentyfourseven': 'Twenty Four Seven / טוונטי פור סבן',
        'renuar': 'Renuar / רנואר',
        'castro': 'Castro / קסטרו',
        '365': '365 / שלוש שישים וחמש',
        'ace': 'ACE / אייס',
        'shoresh': 'Shoresh / שורש',
        'zer4u': 'ZER4U / זר פור יו',
        'hosamtov': 'Hosam Tov / חוסם טוב',
        'nautica': 'Nautica / נאוטיקה',
        'dynamica': 'Dynamica / דינמיקה',
        'magnolia': 'Magnolia Jeans / מגנוליה ג\'ינס',
        'intimaya': 'Intimaya / אינטימיה',
        'noizz': 'NOIZZ / נויז',
        'replay': 'Replay / ריפליי',
        'olam': 'Olam Hakitniyot / עולם הקטניות',
        'timberland': 'Timberland / טימברלנד',
        'children': 'Children\'s Place / צ\'ילדרן',
        'sebras': 'Sebras / סברס'
    }
    
    # Get the full name from the dictionary, or use a formatted version of the store slug if not found
    store_name = store_names.get(store, store.replace('-', ' ').title())
    
    context = {
        'store_name': store_name,
        'message': 'No coupons found'
    }
    return render(request, 'intellishop/coupon_detail.html', context)

def filter_search(request):
    print("Debug: Accessing filter_search view")  # Add debug print
    return render(request, 'intellishop/filter_search.html')

def profile_view(request):
    
    # Get user from session
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    
    user = User.find_one({'_id': ObjectId(user_id)})
    if not user:
        return redirect('login')

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_username':
            new_username = request.POST.get('username')
            # Add validation and email verification here
            User.update_one({'_id': ObjectId(user_id)}, {'$set': {'username': new_username}})
            
        elif action == 'update_password':
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            if user.get('password') == current_password and new_password == confirm_password:
                # Add email verification here
                User.update_one({'_id': ObjectId(user_id)}, {'$set': {'password': new_password}})
            
        elif action == 'delete_account':
            # Add email verification here
            User.delete_one({'_id': ObjectId(user_id)})
            return redirect('logout')

    context = {
        'username': user.get('username'),
        'email': user.get('email')
    }
    return render(request, 'intellishop/profile.html', context)

def logout_view(request):
    # Clear the session
    request.session.flush()
    # Redirect to home page or login page
    return redirect('login')

def coupon_code_view(request, code):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, 'intellishop', 'data', 'coupon_samples.json')
    
    # Add fallback path if the primary one doesn't exist
    if not os.path.exists(json_path):
        alt_json_path = os.path.join(base_dir, 'data', 'coupon_samples.json')
        if os.path.exists(alt_json_path):
            json_path = alt_json_path
    
    try:
        with open(json_path, 'r') as f:
            coupons = json.load(f)
            # Case-insensitive comparison
            coupon = next((c for c in coupons if c['code'].upper() == code.upper()), None)
            
            if coupon:
                formatted_coupon = {
                    'code': coupon['code'],
                    'amount': f"{coupon['amount']}%" if coupon['discount_type'] == 'percent' else f"${coupon['amount']}",
                    'minimum_amount': coupon['minimum_amount'],
                }
                return render(request, 'intellishop/coupon_code.html', {'coupon': formatted_coupon})
            
    except Exception as e:
        print(f"Error loading coupon: {e}")
    
    # If we get here, redirect to home instead of showing error
    return redirect('index_home')

