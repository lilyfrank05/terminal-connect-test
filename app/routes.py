from flask import Blueprint, render_template, request, current_app, jsonify, flash, redirect, url_for
import requests
import json

bp = Blueprint('main', __name__)

ENVIRONMENT_URLS = {
    'production': 'https://api-terminal-gateway.tillpayments.com/devices',
    'sandbox': 'https://api-terminal-gateway.tillvision.show/devices'
}

def validate_config():
    """Validate that all required configuration values are set"""
    required_configs = ['MID', 'TID', 'API_KEY', 'POSTBACK_URL', 'BASE_URL']
    missing = [config for config in required_configs if not current_app.config.get(config)]
    
    if missing:
        flash(f'Missing configuration: {", ".join(missing)}. Please configure these values first.', 'danger')
        return False
    return True

def make_api_request(endpoint, method='POST', payload=None):
    """Helper function to make API requests with proper headers and error handling"""
    if not validate_config():
        return None, "Missing configuration values"
        
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': current_app.config["API_KEY"]
    }
    
    url = f"{current_app.config['BASE_URL']}{endpoint}"
    
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.RequestException as e:
        error_message = str(e)
        if hasattr(e.response, 'json'):
            try:
                error_data = e.response.json()
                error_message = error_data.get('message', str(e))
            except:
                pass
        return None, error_message

def process_intent(intent_id):
    """Helper function for the second API call to process the intent"""
    if not validate_config():
        return None, "Missing configuration values"
        
    endpoint = f"/merchant/{current_app.config['MID']}/intent/{intent_id}/process"
    payload = {
        "tid": current_app.config['TID']
    }
    
    response_data, error = make_api_request(endpoint, payload=payload)
    
    if error:
        flash(f'Process failed for Intent ID {intent_id}: {error}', 'danger')
    else:
        flash(f'Successfully processed Intent ID: {intent_id}', 'success')
    
    return response_data, error

@bp.route('/')
def index():
    return redirect(url_for('main.config'))

@bp.route('/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        # Update configuration
        environment = request.form.get('environment', 'sandbox')
        current_app.config['ENVIRONMENT'] = environment
        current_app.config['BASE_URL'] = ENVIRONMENT_URLS[environment]
        current_app.config['MID'] = request.form.get('mid', '')
        current_app.config['TID'] = request.form.get('tid', '')
        current_app.config['API_KEY'] = request.form.get('api_key', '')
        current_app.config['POSTBACK_URL'] = request.form.get('postback_url', '')
        flash('Configuration updated successfully', 'success')
        return redirect(url_for('main.config'))
    
    return render_template('config.html',
                         environment=current_app.config.get('ENVIRONMENT', 'sandbox'),
                         mid=current_app.config.get('MID', ''),
                         tid=current_app.config.get('TID', ''),
                         api_key=current_app.config.get('API_KEY', ''),
                         postback_url=current_app.config.get('POSTBACK_URL', ''))

@bp.route('/sale', methods=['GET', 'POST'])
def sale():
    if request.method == 'POST':
        if not validate_config():
            return redirect(url_for('main.config'))
            
        try:
            amount = float(request.form.get('amount', 0))
            if amount <= 0:
                flash('Amount must be greater than 0', 'danger')
                return redirect(url_for('main.sale'))
        except ValueError:
            flash('Invalid amount value', 'danger')
            return redirect(url_for('main.sale'))
            
        merchant_reference = request.form.get('merchant_reference')
        if not merchant_reference:
            flash('Merchant reference is required', 'danger')
            return redirect(url_for('main.sale'))
        
        # First API call to create payment intent
        endpoint = f"/merchant/{current_app.config['MID']}/intent/payment"
        payload = {
            "subTotal": int(amount * 100),
            "merchantReference": merchant_reference,
            "postbackUrl": current_app.config['POSTBACK_URL']
        }
        
        response_data, error = make_api_request(endpoint, payload=payload)
        
        if error:
            flash(f'Error creating payment intent: {error}', 'danger')
            return redirect(url_for('main.sale'))
        
        # Second API call to process the intent
        intent_id = response_data['intentId']
        process_intent(intent_id)
        
        return redirect(url_for('main.sale'))
    
    return render_template('sale.html')

@bp.route('/unlinked-refund', methods=['GET', 'POST'])
def unlinked_refund():
    if request.method == 'POST':
        if not validate_config():
            return redirect(url_for('main.config'))
            
        try:
            amount = float(request.form.get('amount', 0))
            if amount <= 0:
                flash('Amount must be greater than 0', 'danger')
                return redirect(url_for('main.unlinked_refund'))
        except ValueError:
            flash('Invalid amount value', 'danger')
            return redirect(url_for('main.unlinked_refund'))
            
        merchant_reference = request.form.get('merchant_reference')
        if not merchant_reference:
            flash('Merchant reference is required', 'danger')
            return redirect(url_for('main.unlinked_refund'))
        
        # First API call to create refund intent
        endpoint = f"/merchant/{current_app.config['MID']}/intent/refund"
        payload = {
            "amount": int(amount * 100),
            "merchantReference": merchant_reference,
            "postbackUrl": current_app.config['POSTBACK_URL']
        }
        
        response_data, error = make_api_request(endpoint, payload=payload)
        
        if error:
            flash(f'Error creating refund intent: {error}', 'danger')
            return redirect(url_for('main.unlinked_refund'))
        
        # Second API call to process the intent
        intent_id = response_data['intentId']
        process_intent(intent_id)
        
        return redirect(url_for('main.unlinked_refund'))
    
    return render_template('unlinked_refund.html')

@bp.route('/linked-refund', methods=['GET', 'POST'])
def linked_refund():
    if request.method == 'POST':
        if not validate_config():
            return redirect(url_for('main.config'))
            
        try:
            amount = float(request.form.get('amount', 0))
            if amount <= 0:
                flash('Amount must be greater than 0', 'danger')
                return redirect(url_for('main.linked_refund'))
        except ValueError:
            flash('Invalid amount value', 'danger')
            return redirect(url_for('main.linked_refund'))
            
        merchant_reference = request.form.get('merchant_reference')
        if not merchant_reference:
            flash('Merchant reference is required', 'danger')
            return redirect(url_for('main.linked_refund'))
            
        parent_intent_id = request.form.get('parent_intent_id')
        if not parent_intent_id:
            flash('Parent Intent ID is required', 'danger')
            return redirect(url_for('main.linked_refund'))

        via_pinpad = request.form.get('via_pinpad', 'yes') == 'yes'
        
        if not via_pinpad:
            # First get the parent intent details
            endpoint = f"/merchant/{current_app.config['MID']}/intent/{parent_intent_id}"
            response_data, error = make_api_request(endpoint, method='GET')
            
            if error:
                flash(f'Error fetching parent intent details: {error}', 'danger')
                return redirect(url_for('main.linked_refund'))
                
            # Parse the externalData JSON string
            try:
                external_data = json.loads(response_data['transactionDetails']['externalData'])
                transaction_details = {
                    "gatewayReferenceNumber": external_data['gatewayReferenceNumber'],
                    "originalAmount": external_data['originalAmount'],
                    "originalApprovalCode": external_data['originalApprovalCode'],
                    "originalTransactionType": external_data['originalTransactionType'],
                    "mid": external_data['hostMerchantId'],
                    "tid": external_data['hostTerminalId']
                }
            except (KeyError, json.JSONDecodeError) as e:
                flash(f'Error parsing transaction details: {str(e)}', 'danger')
                return redirect(url_for('main.linked_refund'))
        
        # Create refund intent
        endpoint = f"/merchant/{current_app.config['MID']}/intent/refund"
        payload = {
            "amount": int(amount * 100),
            "merchantReference": merchant_reference,
            "postbackUrl": current_app.config['POSTBACK_URL'],
            "parentIntentId": parent_intent_id
        }

        if not via_pinpad:
            payload["isNonPinpadRefund"] = True
            payload["transactionDetails"] = transaction_details
        
        response_data, error = make_api_request(endpoint, payload=payload)
        
        if error:
            flash(f'Error creating linked refund intent: {error}', 'danger')
            return redirect(url_for('main.linked_refund'))
        
        # Get the intent ID from the response
        intent_id = response_data['intentId']

        if via_pinpad:
            # Process via pinpad (existing flow)
            process_intent(intent_id)
        else:
            # When not using pinpad, we don't need to make the second API call
            flash(f'Refund intent {intent_id} created successfully!', 'success')
        
        return redirect(url_for('main.linked_refund'))
    
    return render_template('linked_refund.html')

@bp.route('/reversal', methods=['GET', 'POST'])
def reversal():
    if request.method == 'POST':
        if not validate_config():
            return redirect(url_for('main.config'))
            
        merchant_reference = request.form.get('merchant_reference')
        if not merchant_reference:
            flash('Merchant reference is required', 'danger')
            return redirect(url_for('main.reversal'))
            
        parent_intent_id = request.form.get('parent_intent_id')
        if not parent_intent_id:
            flash('Parent Intent ID is required', 'danger')
            return redirect(url_for('main.reversal'))
        
        # First API call to create reversal intent
        endpoint = f"/merchant/{current_app.config['MID']}/intent/reversal"
        payload = {
            "merchantReference": merchant_reference,
            "postbackUrl": current_app.config['POSTBACK_URL'],
            "parentIntentId": parent_intent_id
        }
        
        response_data, error = make_api_request(endpoint, payload=payload)
        
        if error:
            flash(f'Error creating reversal intent: {error}', 'danger')
            return redirect(url_for('main.reversal'))
        
        # Second API call to process the intent
        intent_id = response_data['intentId']
        process_intent(intent_id)
        
        return redirect(url_for('main.reversal'))
    
    return render_template('reversal.html')
