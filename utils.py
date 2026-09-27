from kavenegar import KavenegarAPI, APIException, HTTPException
import random

# # تولید کد OTP 6 رقمی تصادفی
def generate_otp():
    return random.randint(100000, 999999)

def send_otp_to_phone(phone_number, otp_code):
    try:
        api = KavenegarAPI('6D4B7557415A7974556D37755977535830755A72476250327035484E674147634C586F376F544B56684E343D')  # جایگزین کردن با کلید API خود
        params = {
            'receptor': phone_number,
            'template': 'goldestone',
            'token': str(otp_code),
            'type': 'sms'
        }
        api.verify_lookup(params)
    except APIException as e:
        print('APIException:', e)
    except HTTPException as e:
        print('HTTPException:', e)