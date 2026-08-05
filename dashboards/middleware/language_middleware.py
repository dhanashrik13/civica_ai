from django.utils.deprecation import MiddlewareMixin
from django.utils import translation

class AutoDetectLanguageMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # 1. Get current language as determined by LocaleMiddleware (Cookie/Session/Browser)
        current_lang = translation.get_language()
        
        # 2. Sync our custom session key 'lang' if it differs
        # This ensures that if the user used set_language, our 'lang' key is updated.
        if request.session.get("lang") != current_lang:
            request.session["lang"] = current_lang
        
        # 3. If no language was detected/set at all (should not happen with LocaleMiddleware)
        # we can keep the browser detection as a fallback, but LocaleMiddleware already does this.
        if not current_lang:
            browser_lang = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
            if browser_lang:
                browser_lang = browser_lang.split(',')[0].split('-')[0]
            
            supported = ['en', 'hi', 'mr']
            target_lang = browser_lang if browser_lang in supported else 'en'
            translation.activate(target_lang)
            request.session['lang'] = target_lang
