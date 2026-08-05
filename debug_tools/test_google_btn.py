import os
import django
from django.conf import settings
from django.template import Template, Context
from django.test import RequestFactory

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_proj.settings')
django.setup()

from django.test import Client
c = Client()
response = c.get('/accounts/login/citizen/')
print(f'Status: {response.status_code}')
if 'Continue with Google' in response.content.decode():
    print('Found button')
    # Extract the href value
    import re
    match = re.search(r'href="([^"]+google[^"]+)"', response.content.decode())
    if match:
        print(f'URL: {match.group(1)}')
    else:
        print('URL not found in template')
else:
    print('Button not found')
