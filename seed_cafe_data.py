import os
import django
import random
import uuid
from decimal import Decimal
from io import BytesIO
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')  # Change this to your project name
django.setup()

from django.contrib.auth import get_user_model
from pos.models import (
    Floor, Table, Category, Product, ProductVariant,
    PaymentMethod, POSSession
)

User = get_user_model()

def create_cafe_image(product_name, category_name, price):
    """Generate cafe-style product image"""
    width, height = 400, 300
    image = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(image)
    
    # Cafe-style color schemes
    color_schemes = {
        'Deserts': [(255, 218, 185), (255, 160, 122)],
        'Fastfood': [(255, 215, 0), (255, 140, 0)],
        'Hot Drinks': [(139, 69, 19), (101, 67, 33)],
        'Cold Drinks': [(135, 206, 235), (70, 130, 180)],
        'Snacks': [(255, 228, 181), (218, 165, 32)],
        'Breakfast': [(255, 250, 240), (255, 222, 173)],
        'Extra Toppings': [(220, 220, 220), (169, 169, 169)],
        'Combos': [(218, 165, 32), (184, 134, 11)],
    }
    
    colors = color_schemes.get(category_name, [(218, 165, 32), (184, 134, 11)])
    
    # Create gradient
    for y in range(height):
        r = int(colors[0][0] + (colors[1][0] - colors[0][0]) * y / height)
        g = int(colors[0][1] + (colors[1][1] - colors[0][1]) * y / height)
        b = int(colors[0][2] + (colors[1][2] - colors[0][2]) * y / height)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # Draw a plate
    center_x, center_y = width//2, height//2 - 30
    draw.ellipse([center_x-60, center_y-40, center_x+60, center_y+40], 
                outline=(255,255,255), width=2)
    
    # Add text
    try:
        font = ImageFont.truetype("arial.ttf", 22)
        small_font = ImageFont.truetype("arial.ttf", 18)
    except:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    # Product name
    name_text = product_name[:20] + "..." if len(product_name) > 20 else product_name
    text_x = (width - len(name_text) * 12) // 2
    text_y = height - 70
    
    draw.rectangle([text_x-10, text_y-5, text_x+len(name_text)*12+10, text_y+30], 
                  fill=(0,0,0,180))
    draw.text((text_x, text_y), name_text, fill=(255,255,255), font=font)
    
    # Price
    price_text = f"Rs.{price}"
    price_x = (width - len(price_text) * 10) // 2
    price_y = height - 35
    draw.text((price_x, price_y), price_text, fill=(255,215,0), font=small_font)
    
    buffer = BytesIO()
    image.save(buffer, format='PNG', quality=85)
    buffer.seek(0)
    
    return ContentFile(buffer.read(), name=f"{product_name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}.png")

def seed_data():
    print("☕ Seeding Indian Cafe data...")
    
    # Create admin user
    admin, created = User.objects.get_or_create(
        username='admin',
        defaults={
            'email': 'admin@cafe.com',
            'first_name': 'Cafe',
            'last_name': 'Owner',
            'is_staff': True,
            'is_superuser': True,
        }
    )
    if created:
        admin.set_password('admin123')
        admin.save()
        print("✅ Created admin user (admin/admin123)")
    
    # Create Floors
    floors = []
    floor_names = ["Ground Floor - Cafe Area", "First Floor - Family Section", "Terrace - Open Air"]
    for name in floor_names:
        floor, _ = Floor.objects.get_or_create(name=name, defaults={'is_active': True})
        floors.append(floor)
    
    # Create Tables
    table_configs = [
        (floors[0], 1, 2, "Window Seat"), (floors[0], 2, 4, "Corner"), 
        (floors[0], 3, 2, "Bar Counter"), (floors[0], 4, 6, "Family Table"),
        (floors[0], 5, 4, "Center"), (floors[0], 6, 2, "Cozy Corner"),
        (floors[1], 7, 8, "Party Area"), (floors[1], 8, 4, "Balcony"),
        (floors[2], 9, 6, "Terrace"), (floors[2], 10, 4, "Garden View"),
    ]
    
    for floor, num, seats, resource in table_configs:
        Table.objects.get_or_create(
            floor=floor, number=num,
            defaults={'seats': seats, 'appointment_resource': resource}
        )
    
    # Create Categories
    categories_data = [
        ("Breakfast", True, 10),
        ("Snacks", True, 20),
        ("Fastfood", True, 30),
        ("Hot Drinks", False, 40),
        ("Cold Drinks", False, 45),
        ("Deserts", False, 50),
        ("Extra Toppings", True, 60),
        ("Breakfast Combos", True, 15),
        ("Snack Combos", True, 25),
        ("Fastfood Combos", True, 35),
    ]
    
    categories = []
    for name, send_to_kitchen, order in categories_data:
        cat, _ = Category.objects.get_or_create(
            name=name,
            defaults={'send_to_kitchen': send_to_kitchen, 'display_order': order}
        )
        categories.append(cat)
    
    # Create Products
    products_data = [
        # Breakfast
        (categories[0], "Masala Dosa", 80, "plate", 5, "Crispy dosa with potato filling"),
        (categories[0], "Idli Sambhar", 60, "plate", 5, "2 pieces idli with sambhar"),
        (categories[0], "Vada Pav", 40, "piece", 5, "Mumbai style vada pav"),
        (categories[0], "Poha", 50, "bowl", 5, "Flattened rice with peanuts"),
        (categories[0], "Aloo Paratha", 70, "piece", 5, "Stuffed flatbread with butter"),
        
        # Snacks
        (categories[1], "Samosa", 30, "piece", 5, "Crispy pastry with spiced potato"),
        (categories[1], "Kachori", 35, "piece", 5, "Flaky pastry with lentil filling"),
        (categories[1], "Dhokla", 60, "plate", 5, "Steamed gram flour cake"),
        (categories[1], "Bhel Puri", 50, "bowl", 5, "Puffed rice with chutneys"),
        (categories[1], "Pani Puri", 40, "plate", 5, "6 pieces with spicy water"),
        (categories[1], "French Fries", 60, "plate", 5, "Crispy fries with dip"),
        
        # Fastfood
        (categories[2], "Veg Burger", 80, "burger", 5, "Veg patty with lettuce"),
        (categories[2], "Chicken Burger", 120, "burger", 5, "Grilled chicken burger"),
        (categories[2], "Veg Cheese Sandwich", 70, "sandwich", 5, "Grilled sandwich with cheese"),
        (categories[2], "Club Sandwich", 110, "sandwich", 5, "Triple-decker sandwich"),
        (categories[2], "Veg Pizza", 150, "pizza", 5, "6-inch veg pizza"),
        (categories[2], "Frankie Roll", 80, "roll", 5, "Veg frankie roll"),
        
        # Hot Drinks
        (categories[3], "Filter Coffee", 25, "cup", 5, "South Indian filter coffee"),
        (categories[3], "Masala Chai", 20, "cup", 5, "Spiced Indian tea"),
        (categories[3], "Ginger Tea", 20, "cup", 5, "Fresh ginger tea"),
        (categories[3], "Hot Chocolate", 60, "cup", 5, "Rich hot chocolate"),
        
        # Cold Drinks
        (categories[4], "Cold Coffee", 60, "glass", 5, "Chilled coffee with ice cream"),
        (categories[4], "Iced Tea", 50, "glass", 0, "Lemon iced tea"),
        (categories[4], "Fresh Lime Soda", 40, "glass", 0, "Sweet or salty"),
        (categories[4], "ButterMilk", 30, "glass", 0, "Chaas with spices"),
        (categories[4], "Lassi", 50, "glass", 0, "Sweet or salty lassi"),
        (categories[4], "Mango Shake", 80, "glass", 0, "Fresh mango milkshake"),
        (categories[4], "Soft Drinks", 40, "bottle", 0, "Coke, Sprite, etc"),
        
        # Deserts
        (categories[5], "Gulab Jamun", 60, "plate", 5, "2 pieces with syrup"),
        (categories[5], "Jalebi", 50, "plate", 5, "Crispy spiral sweets"),
        (categories[5], "Rasgulla", 60, "plate", 5, "2 pieces spongy balls"),
        (categories[5], "Ice Cream", 70, "scoop", 0, "Vanilla, chocolate, strawberry"),
        (categories[5], "Brownie", 80, "piece", 5, "Chocolate brownie"),
        
        # Extra Toppings
        (categories[6], "Extra Cheese", 30, "portion", 5, "Extra cheese topping"),
        (categories[6], "Extra Mayo", 20, "portion", 0, "Mayonnaise"),
        (categories[6], "Extra Paneer", 50, "portion", 5, "Extra cottage cheese"),
        
        # Breakfast Combos
        (categories[7], "Idli Vada Combo", 90, "combo", 5, "2 idli + 1 vada + sambhar"),
        (categories[7], "Dosa Combo", 120, "combo", 5, "Masala dosa + coffee"),
        
        # Snack Combos
        (categories[8], "Samosa Chaat Combo", 80, "combo", 5, "2 samosa + chutney"),
        (categories[8], "Bhelpuri Combo", 80, "combo", 5, "Bhelpuri + cold drink"),
        
        # Fastfood Combos
        (categories[9], "Burger Combo", 150, "combo", 5, "Burger + fries + drink"),
        (categories[9], "Pizza Combo", 220, "combo", 5, "Pizza + garlic bread + drink"),
    ]
    
    product_count = 0
    for cat, name, price, unit, tax, desc in products_data:
        product, created = Product.objects.get_or_create(
            name=name,
            category=cat,
            defaults={
                'price': price,
                'unit': unit,
                'tax_rate': tax,
                'description': desc,
                'is_available': True
            }
        )
        if created:
            # Generate and save image
            try:
                image_file = create_cafe_image(name, cat.name, price)
                product.image.save(image_file.name, image_file, save=True)
                product_count += 1
                print(f"  ✓ Added {name} with image")
            except Exception as e:
                print(f"  ✓ Added {name} (image failed: {e})")
    
    # Create Payment Methods
    PaymentMethod.objects.get_or_create(
        type='cash',
        defaults={'is_enabled': True}
    )
    PaymentMethod.objects.get_or_create(
        type='digital',
        defaults={'is_enabled': True}
    )
    PaymentMethod.objects.get_or_create(
        type='upi',
        defaults={'is_enabled': True, 'upi_id': 'cafe@okhdfcbank'}
    )
    
    print("\n" + "="*50)
    print("✅ Cafe data seeded successfully!")
    print(f"   - {User.objects.count()} users")
    print(f"   - {Floor.objects.count()} floors")
    print(f"   - {Table.objects.count()} tables")
    print(f"   - {Category.objects.count()} categories")
    print(f"   - {product_count} products with images")
    print(f"   - {PaymentMethod.objects.count()} payment methods")
    print("="*50)
    print("\n📝 Login credentials:")
    print("   Username: admin")
    print("   Password: admin123")

if __name__ == "__main__":
    seed_data()