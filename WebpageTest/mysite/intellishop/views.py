# View functions that handle HTTP requests and return responses
from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models.mongodb_models import Product, User, Coupon
import json
from pymongo.errors import DuplicateKeyError
from bson.objectid import ObjectId

def index(request):
    return render(request, 'intellishop/index.html')

def index_home(request):
    return render(request, 'intellishop/index_home_original.html')

def login_view(request):
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

def product_list(request):
    """View to list products, optionally filtered by category"""
    category = request.GET.get('category', None)
    
    if category:
        products = Product.get_by_category(category)
    else:
        products = Product.find()
    
    # Convert ObjectId to string for JSON serialization
    for product in products:
        if product and '_id' in product:
            product['_id'] = str(product['_id'])
    
    return JsonResponse({'products': products})

def product_detail(request, product_id):
    """View to display a specific product"""
    product = Product.get_by_id(product_id)
    
    if not product:
        return JsonResponse({'error': 'Product not found'}, status=404)
    
    # Convert ObjectId to string for JSON serialization
    product['_id'] = str(product['_id'])
    
    return JsonResponse({'product': product})

def aliexpress_coupons(request):
    # Get all active coupons from the database
    coupons = Coupon.get_active_coupons()
    
    # Convert ObjectId to string for JSON serialization
    for coupon in coupons:
        if coupon and '_id' in coupon:
            coupon['_id'] = str(coupon['_id'])
    
    return render(request, 'intellishop/coupon_for_aliexpress.html', {'coupons': coupons})

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

