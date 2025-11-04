# accounts/middleware.py
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.contrib import messages

class DisableBackAfterLogoutMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        # Prevent browser from caching authenticated pages
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
