from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User


# ----------------------------------------------------------------------
# Signup Form - handles new user registration with custom fields
# ----------------------------------------------------------------------
# We're extending Django's built-in UserCreationForm to add email, phone,
# and role selection. This gives us all the password validation and hashing
# for free while letting us collect the extra info our app needs.
# ----------------------------------------------------------------------
class SignupForm(UserCreationForm):
    # Email is required - we'll use this for important notifications and account recovery
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'form-input',
        'placeholder': 'Email address'
    }))
    
    # Phone is optional for now, but we might require it later for SMS notifications
    # Keeping max_length at 15 to accommodate most international numbers
    phone = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={
        'class': 'form-input',
        'placeholder': 'Phone number (optional)'
    }))
    
    # Role determines what permissions the user gets in the system
    # Choices are defined in the User model's ROLE_CHOICES constant
    role = forms.ChoiceField(choices=User.ROLE_CHOICES, required=True, widget=forms.Select(attrs={
        'class': 'form-select'
    }))
    
    class Meta:
        model = User
        # These fields will appear in the form in this specific order
        fields = ('username', 'email', 'phone', 'role', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Username'}),
        }
    
    # Overriding save() to ensure our custom fields are properly saved to the user instance
    # The parent class handles password hashing and the core user fields
    def save(self, commit=True):
        user = super().save(commit=False)  # Create user object but don't save to DB yet
        user.email = self.cleaned_data['email']
        user.phone = self.cleaned_data['phone']
        user.role = self.cleaned_data['role']
        if commit:
            user.save()  # Now persist everything to the database
        return user


# ----------------------------------------------------------------------
# Login Form - just styling the default authentication form
# ----------------------------------------------------------------------
# Nothing fancy here - we're just adding CSS classes and placeholders to the
# default AuthenticationForm to match our frontend design system.
# The parent class already handles all the authentication logic.
# ----------------------------------------------------------------------
class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-input',
        'placeholder': 'Username'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-input',
        'placeholder': 'Password'
    }))