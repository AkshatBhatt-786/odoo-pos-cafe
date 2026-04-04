from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

# ----------------------------------------------------------------------
# Custom User Model - extending Django's AbstractUser
# ----------------------------------------------------------------------
# We're not using the default User model because we need role-based permissions
# and additional fields for tracking session states. Extending AbstractUser
# gives us all the built-in auth features (passwords, permissions, groups)
# while letting us add our own business logic.
# ----------------------------------------------------------------------
class User(AbstractUser):
    # Role definitions - keep these sorted by hierarchy for readability
    # Adding new roles? Make sure to update permission checks across the app
    ROLE_CHOICES = [
        ('admin', 'Administrator'),      # Full system access
        ('manager', 'Manager'),          # Can manage users and view reports
        ('cashier', 'Cashier'),           # Front-of-house, processes orders/payments
        ('kitchen', 'Kitchen Staff'),     # Back-of-house, only sees order tickets
    ]
    
    # The user's primary role in the system - defaulting to cashier since that's
    # our most common user type. Limited to 20 chars based on our longest role name.
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='cashier')
    
    # Optional contact field - keeping it nullable because some staff members
    # don't want to share personal numbers. Blank=True handles forms nicely.
    phone = models.CharField(max_length=15, blank=True, null=True)
    
    # Tracks if user has an active POS session open on a terminal
    # Used to prevent multiple concurrent logins on different devices
    is_active_session = models.BooleanField(default=False)
    
    # References the specific session ID in our SessionLog model
    # Null/blank allowed because user might not have an active session right now
    current_session_id = models.IntegerField(null=True, blank=True)
    
    # Auto-populated timestamps for audit trails and debugging
    # auto_now_add sets once on creation, auto_now updates on every save
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Human-readable representation - useful in admin panel, logs, and debugging
    # Shows both username and role so you can identify who's who at a glance
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    class Meta:
        db_table = 'users'  # Explicit table name to avoid Django's default "auth_user" naming