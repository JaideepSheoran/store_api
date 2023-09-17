from math import floor
from random import random
import time
import datetime
from bson import ObjectId
from flask import Flask, jsonify, make_response, request
from flask_cors import CORS
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import jwt


app = Flask(__name__, template_folder='templates')
CORS(app)

# Setup MongoDB Connection with **** ShopManager ****
app.config['MONGO_URI'] =  "mongodb+srv://jaideepsinghsheoran:jaideep123@cluster0.sme0l7z.mongodb.net/shopmanager"
app.config['SECRET_KEY'] = "jaideepsinghsheoranisbacktobuisness"

# Mail Setup
MAIL = Mail(app)
app.config['MAIL_SERVER']='smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = 'shopmanagersoftware@gmail.com'
app.config['MAIL_PASSWORD'] = 'gbjenljbxmlyaxim'
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
MAIL = Mail(app)


# Collections in Database **** ShopManager ****
OWNERS = PyMongo(app).db.owners
SHOPS = PyMongo(app).db.shops
CATAGORY = PyMongo(app).db.catagory
ITEMS = PyMongo(app).db.items
OTP_STORE = PyMongo(app).db.otp_store

# Password Hashing
HASH = Bcrypt(app)

# CRUD on OWNER

def generate_otp():
    otp = ""

    digits = "0123456789"

    for _ in range(4):
        otp = otp + digits[floor(10 * random())]

    return otp

@app.route('/send-otp/<string:email>', methods=['GET'])
def sent_otp(email):
    sender = 'shopmanagersoftware@gmail.com'
    recipients = [email]

    msg = Message('OTP for Email Verification', sender=sender, recipients=recipients)
    otp = generate_otp()
    msg.body = f'OTP for email verification is {otp}'
    
    try:
        MAIL.send(msg)
        OTP_STORE.insert_one({'email' : email, 'otp' : otp})
    except:
        return 'Cannot send OTP.' , 500

    return 'OTP sent successfully.' , 200



@app.route('/verify_otp/<string:email>', methods=['POST'])
def verify_otp(email):
    user_otp = request.get_json().get('OTP')
    try:
        stored_otp = OTP_STORE.find_one({'email' : email})
        if stored_otp and user_otp == stored_otp['otp']:
            OTP_STORE.delete_one({'email' : email})  # OTP verified, remove from storage
            return 'OTP verified successfully', 200
        else:
            return 'Wrong OTP', 401
    except:

        return 'Error: Cannot Verify OTP.', 500


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('access_token')

        if not token:
            return jsonify({'message': 'Token is missing'}), 401

        try:
            # Decode the JWT token
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = OWNERS.find_one({'_id': ObjectId(data['user_id'])})

        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token'}), 401
        except Exception as e:
            return jsonify({'message': 'An error occurred', 'error': str(e)}), 500

        if not current_user:
            return jsonify({'message': 'User not found'}), 401

        # Store the user in the request context for further use
        request.current_user = current_user
        return f(*args, **kwargs)

    return decorated_function




# Signup Route
@app.route('/signup/', methods=['POST'])
def signup():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Email and password are required'}), 400

    existing_user = OWNERS.find_one({'email': data['email']})

    if existing_user:
        return jsonify({'message': 'Email already exists'}), 409

    hashed_password = generate_password_hash(data['password'], method='sha256')

    new_user = {
        'email' : data['email'],
        'verified' : False,
        'password' : hashed_password,
        'owner' : data['owner'].capitalize(),
        'phone' : data['phone']
    }

    inserted_user = OWNERS.insert_one(new_user)
    user_id = str(inserted_user.inserted_id)

    token_payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)  # Token expires in 1 hour
    }
    token = jwt.encode(token_payload, app.config['SECRET_KEY'], algorithm='HS256')


    response = make_response(jsonify({'message': 'User registered successfully', 'user_id': user_id}))
    response.set_cookie('access_token', token, httponly=True, max_age=3600)  # Set the cookie with a 1-hour expiration
    return response, 201


@app.route('/login/', methods=['POST'])
def login_account():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Username and password are required'}), 400

    existing_user = OWNERS.find_one({'email': data['email']})
    if not existing_user or not check_password_hash(existing_user['password'], data['password']):
        return jsonify({'message': 'Invalid username or password'}), 401

    user_id = str(existing_user['_id'])

    token_payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)  # Token expires in 1 hour
    }
    token = jwt.encode(token_payload, app.config['SECRET_KEY'], algorithm='HS256')

    # Create a response and set the JWT token as a cookie
    response = make_response(jsonify({'message': 'Login successful', 'user_id': user_id}))
    response.set_cookie('access_token', token, httponly=True, max_age=3600)  # Set the cookie with a 1-hour expiration
    return response, 200
    

@app.route('/logout', methods=['POST'])
def logout():
    # Create a response to clear the 'access_token' cookie
    response = make_response(jsonify({'message': 'Logout successful'}))
    response.delete_cookie('access_token')

    return response, 200

# Create , Read , Update , Delete on ***** SHOPS Collection *****
# Create a new shop

@app.route('/shops/create', methods=['POST'])
@login_required
def create_new_shop():
    shop = request.get_json()
    owner_id = str(request.current_user['_id'])

    address = {
        "pincode" : shop.get('pincode'),
        "city" : shop.get('city'),
        "state" : shop.get('state'),
        "country" : shop.get('country'),
        "street" : shop.get('street')
    }
    type = shop.get('shop_type')

    new_shop = {
        "name" : shop.get('shop_name'),
        "address" : address,
        "shop_type" : type,
        "owner_id" : owner_id
    }

    try:
        shop_added = SHOPS.insert_one(new_shop)
        shop_id = str(shop_added.inserted_id)

        return make_response({'shop' : shop_id}, 200)
    except:
        return make_response({'message' : 'Cannot Create Shop'}, 500)



# Get a shop with given ID
@app.route('/shops/<string:shop_id>', methods=['GET'])
def get_shop(shop_id):
    
    try:
        shop = SHOPS.find_one({"_id" : ObjectId(shop_id)})
        shop["_id"] = str(shop["_id"])
    except:
        return make_response({'message': "NOT FOUND"}, 404)

    return make_response({'message' : shop}, 200)



@app.route('/shops/', methods=['POST'])
def get_all_shops():
    owner = request.get_json()
    try:
        shops = SHOPS.find({"owner_id" : owner.get('owner_id')})
        
        shop_list = []

        for shop in shops:
            shop['_id'] = str(shop['_id'])
            shop_list.append(shop)

        print(shop_list)

    except:
        return make_response({'message': "NOT FOUND"}, 404)

    return make_response(jsonify(shop_list), 200)



# Delete a shop
@app.route('/shops/delete/<string:shop_id>', methods=['DELETE'])
@login_required
def delete_shop(shop_id):

    try:
        shop_status = SHOPS.delete_one({'_id' : ObjectId(shop_id)})
    except:
        return make_response({'message' : f'Unable to delete shop {shop_id}'}, )


    return make_response({'shop' : f"Shop {shop_id} Deleted."}, 200)







# Create , Read , Update , Delete on ***** CATAGORY Collection *****


@app.route('/catagory/<string:shop_id>/create', methods= ['POST'])
@login_required
def create_new_catagory(shop_id):
    catagory_data = request.json()

    new_catagory = {
        "shop_id": shop_id,
        "catagory" : catagory_data.get('catagory').upper(),
        "created_at" : time.time()
    }

    try:
        catagory_added = CATAGORY.insert_one(new_catagory)
    except:
        return make_response({'message' : 'Unable to create..'}, 500)
    
    return make_response({'message' : str(catagory_added.inserted_id)}, 200)


@app.route('/catagory/delete/<string:cat_id>', methods= ['POST'])
@login_required
def delete_catagory(cat_id):

    try:
        delete_items = ITEMS.delete_many({'catagory_id' : ObjectId(cat_id)})
        catagory_deleted = CATAGORY.delete_one({'_id' : ObjectId(cat_id)})
        return make_response({'message' : catagory_deleted}, 200)
    except:
        return make_response({'message' : 'Unable to delete..'}, 500)
    

@app.route('/catagory/<string:shop_id>/get', methods= ['POST'])
def get_catagories(shop_id):

    try:
        catagories = CATAGORY.find({'shop_id' : shop_id})

        cat_list = []

        for catagory in catagories:
            catagory['_id'] = str(catagory['_id'])
            cat_list.append(catagory)

        return make_response(cat_list , 200)
    except:
        return make_response({'message' : 'Unable to fetch categories..'}, 500)





# Create , Read , Update , Delete on ***** ITEMS Collection *****

@app.route('/items/<string:cat_id>/create', methods= ['POST'])
@login_required
def create_new_item(cat_id):

    new_catagory = {
        "catagory_id": cat_id,
        "item" : request.form.get('item').upper(),
        "created_at" : time.time()
    }

    try:
        item_added = CATAGORY.insert_one(new_catagory)
    except:
        return make_response({'message' : 'Unable to create..'}, 500)
    
    return make_response({'message' : str(item_added.inserted_id)}, 200)


@app.route('/items/delete/<string:item_id>', methods= ['POST'])
@login_required
def delete_item(item_id):

    try:
        item_deleted = ITEMS.delete_one({'_id' : ObjectId(item_id)})
        return make_response({'message' : item_deleted}, 200)
    except:
        return make_response({'message' : 'Unable to delete..'}, 500)
    

@app.route('/items/<string:cat_id>/get', methods= ['POST'])
def get_items(cat_id):

    try:
        items = CATAGORY.find({'catagory_id' : cat_id})

        item_list = []

        for item in items:
            item['_id'] = str(item['_id'])
            item_list.append(item)

        return make_response(item_list , 200)
    except:
        return make_response({'message' : 'Unable to fetch items..'}, 500)




if __name__ == '__main__':
    app.run(debug=True, port=5000)