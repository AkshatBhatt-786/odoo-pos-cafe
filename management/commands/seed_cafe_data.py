import random
import uuid
from decimal import Decimal
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.files import File
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

from pos.models import (
    Floor, Table, Category, Product, ProductVariant,
    PaymentMethod, POSSession
)

User = get_user_model()

class Command(BaseCommand):
    help = 'Seed Indian cafe data with images'

    def create_cafe_image(self, product_name, category_name, price):
        """Generate cafe-style product image"""
        width, height = 400, 300
        image = Image.new('RGB', (width, height))
        draw = ImageDraw.Draw(image)
        
        # Cafe-style color schemes
        color_schemes = {
            'Deserts': [(255, 218, 185), (255, 160, 122)],  # Peach/caramel
            'Fastfood': [(255, 215, 0), (255, 140, 0)],  # Golden orange
            'Hot Drinks': [(139, 69, 19), (101, 67, 33)],  # Coffee brown
            'Cold Drinks': [(135, 206, 235), (70, 130, 180)],  # Sky blue
            'Snacks': [(255, 228, 181), (218, 165, 32)],  # Golden
            'Breakfast': [(255, 250, 240), (255, 222, 173)],  # Warm cream
            'Extra Toppings': [(220, 220, 220), (169, 169, 169)],  # Silver/gray
            'Combos': [(218, 165, 32), (184, 134, 11)],  # Rich gold
        }
        
        colors = color_schemes.get(category_name, [(218, 165, 32), (184, 134, 11)])
        
        # Create gradient
        for y in range(height):
            r = int(colors[0][0] + (colors[1][0] - colors[0][0]) * y / height)
            g = int(colors[0][1] + (colors[1][1] - colors[0][1]) * y / height)
            b = int(colors[0][2] + (colors[1][2] - colors[0][2]) * y / height)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        
        # Cafe pattern - coffee cup or food icon
        center_x, center_y = width//2, height//2 - 30
        
        if 'Drinks' in category_name:
            # Draw a cup
            cup_width, cup_height = 80, 100
            draw.ellipse([center_x-cup_width//2, center_y-cup_height//2, 
                         center_x+cup_width//2, center_y+cup_height//2], 
                        outline=(255,255,255), width=3)
            # Handle
            draw.arc([center_x+cup_width//2, center_y-20, center_x+cup_width//2+30, center_y+20], 
                    0, 180, fill=(255,255,255), width=3)
        elif 'Deserts' in category_name:
            # Draw a cake slice
            points = [(center_x, center_y-40), (center_x+40, center_y), 
                     (center_x, center_y+40), (center_x-40, center_y)]
            draw.polygon(points, outline=(255,255,255), width=2)
        else:
            # Draw a plate
            draw.ellipse([center_x-60, center_y-40, center_x+60, center_y+40], 
                        outline=(255,255,255), width=2)
        
        # Add text
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        except:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        
        # Product name
        name_text = product_name[:20] + "..." if len(product_name) > 20 else product_name
        bbox = draw.textbbox((0, 0), name_text, font=font)
        text_x = (width - (bbox[2] - bbox[0])) // 2
        text_y = height - 70
        
        draw.rectangle([text_x-10, text_y-5, text_x+(bbox[2]-bbox[0])+10, text_y+30], 
                      fill=(0,0,0,180))
        draw.text((text_x, text_y), name_text, fill=(255,255,255), font=font)
        
        # Price
        price_text = f"₹{price}"
        bbox = draw.textbbox((0, 0), price_text, font=small_font)
        price_x = (width - (bbox[2] - bbox[0])) // 2
        price_y = height - 35
        draw.text((price_x, price_y), price_text, fill=(255,215,0), font=small_font)
        
        buffer = BytesIO()
        image.save(buffer, format='PNG', quality=85)
        buffer.seek(0)
        
        return ContentFile(buffer.read(), name=f"{product_name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}.png")

    def handle(self, *args, **kwargs):
        self.stdout.write("☕ Seeding Indian Cafe data...")
        
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
            self.stdout.write("✅ Created admin user (admin/admin123)")
        
        # Create Floors
        floors = []
        floor_names = ["Ground Floor - Cafe Area", "First Floor - Family Section", "Terrace - Open Air"]
        for name in floor_names:
            floor, _ = Floor.objects.get_or_create(name=name, defaults={'is_active': True})
            floors.append(floor)
        
        # Create Tables
        table_configs = [
            (floors[0], 1, 2, "Window Seat"), (floors[0], 2, 4, "Corner"), (floors[0], 3, 2, "Bar Counter"),
            (floors[0], 4, 6, "Family Table"), (floors[0], 5, 4, "Center"), (floors[0], 6, 2, "Cozy Corner"),
            (floors[1], 7, 8, "Party Area"), (floors[1], 8, 4, "Balcony"), (floors[2], 9, 6, "Terrace"),
            (floors[2], 10, 4, "Garden View"), (floors[2], 11, 2, "Romantic Corner"),
        ]
        
        for floor, num, seats, resource in table_configs:
            Table.objects.get_or_create(
                floor=floor, number=num,
                defaults={'seats': seats, 'appointment_resource': resource}
            )
        
        # Create Categories (Indian Cafe style)
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
        
        # Create Products with images
        products_data = [
            # Breakfast
            (categories[0], "Masala Dosa", 80, "plate", 5, "Crispy dosa with potato filling"),
            (categories[0], "Idli Sambhar", 60, "plate", 5, "2 pieces idli with sambhar"),
            (categories[0], "Vada Pav", 40, "piece", 5, "Mumbai style vada pav"),
            (categories[0], "Poha", 50, "bowl", 5, "Flattened rice with peanuts"),
            (categories[0], "Upma", 45, "bowl", 5, "Semolina porridge with veggies"),
            (categories[0], "Medu Vada", 50, "plate", 5, "Crispy donut-shaped vada"),
            (categories[0], "Uttapam", 70, "plate", 5, "Thick rice pancake with toppings"),
            (categories[0], "Aloo Paratha", 70, "piece", 5, "Stuffed flatbread with butter"),
            
            # Snacks
            (categories[1], "Samosa", 30, "piece", 5, "Crispy pastry with spiced potato"),
            (categories[1], "Kachori", 35, "piece", 5, "Flaky pastry with lentil filling"),
            (categories[1], "Dhokla", 60, "plate", 5, "Steamed gram flour cake"),
            (categories[1], "Bhel Puri", 50, "bowl", 5, "Puffed rice with chutneys"),
            (categories[1], "Sev Puri", 60, "plate", 5, "Crispy puris with toppings"),
            (categories[1], "Pani Puri", 40, "plate", 5, "6 pieces with spicy water"),
            (categories[1], "French Fries", 60, "plate", 5, "Crispy fries with dip"),
            (categories[1], "Onion Rings", 70, "plate", 5, "Crispy onion rings"),
            
            # Fastfood
            (categories[2], "Veg Burger", 80, "burger", 5, "Veg patty with lettuce"),
            (categories[2], "Chicken Burger", 120, "burger", 5, "Grilled chicken burger"),
            (categories[2], "Veg Cheese Sandwich", 70, "sandwich", 5, "Grilled sandwich with cheese"),
            (categories[2], "Club Sandwich", 110, "sandwich", 5, "Triple-decker sandwich"),
            (categories[2], "Veg Pizza", 150, "pizza", 5, "6-inch veg pizza"),
            (categories[2], "Chicken Pizza", 180, "pizza", 5, "6-inch chicken pizza"),
            (categories[2], "Frankie Roll", 80, "roll", 5, "Veg frankie roll"),
            (categories[2], "Chicken Frankie", 110, "roll", 5, "Chicken frankie roll"),
            (categories[2], "Nachos", 100, "plate", 5, "Nachos with cheese sauce"),
            (categories[2], "Cheese Balls", 90, "plate", 5, "Fried cheese balls"),
            
            # Hot Drinks
            (categories[3], "Filter Coffee", 25, "cup", 5, "South Indian filter coffee"),
            (categories[3], "Masala Chai", 20, "cup", 5, "Spiced Indian tea"),
            (categories[3], "Ginger Tea", 20, "cup", 5, "Fresh ginger tea"),
            (categories[3], "Green Tea", 30, "cup", 0, "Healthy green tea"),
            (categories[3], "Hot Chocolate", 60, "cup", 5, "Rich hot chocolate"),
            (categories[3], "Badam Milk", 50, "glass", 0, "Almond flavored milk"),
            (categories[3], "Bournvita", 40, "cup", 5, "Malt chocolate drink"),
            (categories[3], "Lemon Tea", 25, "cup", 0, "Honey lemon tea"),
            
            # Cold Drinks
            (categories[4], "Cold Coffee", 60, "glass", 5, "Chilled coffee with ice cream"),
            (categories[4], "Iced Tea", 50, "glass", 0, "Lemon iced tea"),
            (categories[4], "Fresh Lime Soda", 40, "glass", 0, "Sweet or salty"),
            (categories[4], "ButterMilk", 30, "glass", 0, "Chaas with spices"),
            (categories[4], "Lassi", 50, "glass", 0, "Sweet or salty lassi"),
            (categories[4], "Mango Shake", 80, "glass", 0, "Fresh mango milkshake"),
            (categories[4], "Chocolate Shake", 70, "glass", 0, "Chocolate milkshake"),
            (categories[4], "Strawberry Shake", 80, "glass", 0, "Strawberry milkshake"),
            (categories[4], "Soft Drinks", 40, "bottle", 0, "Coke, Sprite, etc"),
            (categories[4], "Mineral Water", 20, "bottle", 0, "1 liter"),
            
            # Deserts
            (categories[5], "Gulab Jamun", 60, "plate", 5, "2 pieces with syrup"),
            (categories[5], "Jalebi", 50, "plate", 5, "Crispy spiral sweets"),
            (categories[5], "Rasgulla", 60, "plate", 5, "2 pieces spongy balls"),
            (categories[5], "Ice Cream", 70, "scoop", 0, "Vanilla, chocolate, strawberry"),
            (categories[5], "Brownie", 80, "piece", 5, "Chocolate brownie"),
            (categories[5], "Kulfi", 60, "piece", 0, "Indian ice cream"),
            (categories[5], "Carrot Halwa", 70, "bowl", 5, "Gajar ka halwa"),
            (categories[5], "Payasam", 60, "bowl", 0, "Rice kheer"),
            
            # Extra Toppings
            (categories[6], "Extra Cheese", 30, "portion", 5, "Extra cheese topping"),
            (categories[6], "Extra Mayo", 20, "portion", 0, "Mayonnaise"),
            (categories[6], "Extra Sauce", 15, "portion", 0, "Tomato ketchup"),
            (categories[6], "Extra Paneer", 50, "portion", 5, "Extra cottage cheese"),
            (categories[6], "Extra Chicken", 60, "portion", 5, "Extra grilled chicken"),
            (categories[6], "Extra Butter", 20, "portion", 0, "Butter topping"),
            
            # Breakfast Combos
            (categories[7], "Idli Vada Combo", 90, "combo", 5, "2 idli + 1 vada + sambhar"),
            (categories[7], "Dosa Combo", 120, "combo", 5, "Masala dosa + coffee"),
            (categories[7], "Breakfast Special", 150, "combo", 5, "Poha + samosa + tea"),
            
            # Snack Combos
            (categories[8], "Samosa Chaat Combo", 80, "combo", 5, "2 samosa + chutney"),
            (categories[8], "Bhelpuri Combo", 80, "combo", 5, "Bhelpuri + cold drink"),
            (categories[8], "Snack Platter", 180, "platter", 5, "Samosa, kachori, dhokla"),
            
            # Fastfood Combos
            (categories[9], "Burger Combo", 150, "combo", 5, "Burger + fries + drink"),
            (categories[9], "Pizza Combo", 220, "combo", 5, "Pizza + garlic bread + drink"),
            (categories[9], "Sandwich Combo", 140, "combo", 5, "Sandwich + fries + drink"),
        ]
        
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
                image_file = self.create_cafe_image(name, cat.name, price)
                product.image.save(image_file.name, image_file, save=True)
                self.stdout.write(f"  ✓ Added {name} with image")
        
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
        
        self.stdout.write(self.style.SUCCESS("✅ Cafe data seeded successfully!"))
        self.stdout.write(self.style.SUCCESS(f"   - {Product.objects.count()} products added"))
        self.stdout.write(self.style.SUCCESS(f"   - {Category.objects.count()} categories"))
        self.stdout.write(self.style.SUCCESS(f"   - {Table.objects.count()} tables"))