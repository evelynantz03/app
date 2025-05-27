from flask import Flask, request
import xmlrpc.client
import os

app = Flask(__name__)

ODOO_URL = os.getenv("ODOO_URL")
ODOO_DB = os.getenv("ODOO_DB")
ODOO_USER = os.getenv("ODOO_USER")
ODOO_PASS = os.getenv("ODOO_PASS")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "mi_token_verificacion")

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        return "Token inválido", 403

    if request.method == 'POST':
        data = request.json
        try:
            common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
            uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASS, {})
            models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")

            for entry in data.get("entry", []):
                platform = 'facebook' if 'messaging' in entry else 'instagram'
                events = entry.get("messaging") or entry.get("changes", [])

                for event in events:
                    if platform == 'facebook':
                        sender = event.get("sender", {}).get("id")
                        message = event.get("message", {}).get("text")
                    else:
                        sender = event.get("value", {}).get("from", {}).get("id")
                        message = event.get("value", {}).get("message")

                    if not message:
                        continue

                    # Crear o buscar canal en Odoo
                    channel_name = f"{platform.upper()} - {sender}"
                    channel_ids = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'mail.channel', 'search', [[['name', '=', channel_name]]])
                    if channel_ids:
                        channel_id = channel_ids[0]
                    else:
                        channel_id = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'mail.channel', 'create', [{
                            'name': channel_name,
                            'channel_type': 'channel',
                            'public': 'public',
                        }])

                    # Enviar mensaje
                    models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'mail.channel', 'message_post', [channel_id, {
                        'body': message,
                        'message_type': 'comment',
                        'subtype_xmlid': 'mail.mt_comment',
                    }])

        except Exception as e:
            return f"Error: {str(e)}", 500

        return "EVENT_RECEIVED", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))
