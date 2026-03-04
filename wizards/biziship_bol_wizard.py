import json
import base64
import requests
import io
import os
from odoo import models, fields, api, _
from odoo.exceptions import UserError

from odoo.addons.BiziShipOnOdoo1.api_utils import get_biziship_api_url, get_email2quote_api_key, get_groq_api_key

try:
    from PyPDF2 import PdfReader
except ImportError:
    try:
        from PyPDF2 import PdfFileReader as PdfReader
    except ImportError:
        PdfReader = None

class BizishipBolImportWizard(models.TransientModel):
    _name = 'biziship.bol.import.wizard'
    _description = 'BiziShip BOL Import Wizard'

    bol_file = fields.Binary(string="BOL PDF File", required=True)
    file_name = fields.Char(string="File Name")

    def action_process_bol(self):
        self.ensure_one()
        if not self.bol_file:
            raise UserError(_("Please upload a BOL PDF file."))

        # 1. Base64 PDF string (Odoo Binary fields are already base64 encoded bytes)
        file_base64 = self.bol_file.decode('utf-8')

        # Extract text from the PDF
        pdf_text = ""
        try:
            if PdfReader:
                pdf_bytes = base64.b64decode(self.bol_file)
                reader = PdfReader(io.BytesIO(pdf_bytes))
                pages = reader.pages if hasattr(reader, 'pages') else reader.pages
                for page in pages:
                    text = page.extract_text() if hasattr(page, 'extract_text') else page.extractText()
                    if text:
                        pdf_text += text + "\n"
            else:
                pdf_text = "Error: PyPDF2 library is not available in Odoo to extract text."
        except Exception as e:
            pdf_text = f"Error extracting PDF text: {str(e)}"

        # 2. Call Groq API
        groq_api_key = get_groq_api_key()
        if not groq_api_key:
            raise UserError(_("Groq API Key is not configured in secrets.json"))
            
        groq_endpoint = "https://api.groq.com/openai/v1/chat/completions"

        prompt = """
You are an expert logistics data extractor. I have a Bill of Lading (BOL). 
I need to get Freight details from the document text for an LTL Freight request to be passed to freight brokers.
I am providing the extracted document text below. 
Please parse the text data, and extract the following information in a strict JSON format with exactly these keys:
- "Weight"
- "Dimensions"
- "Origin"
- "Destination"
- "Freight Class"

Respond ONLY with a valid JSON object, without any markdown formatting, backticks, or additional explanation.
"""

        headers = {
            "Authorization": f"Bearer {groq_api_key}",
            "Content-Type": "application/json"
        }

        # Use a model that supports large context / JSON mode
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful logistics assistant that outputs data in strict JSON."
                },
                {
                    "role": "user",
                    "content": f"{prompt}\n\nDocument Text:\n{pdf_text}"
                }
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        try:
            response = requests.post(groq_endpoint, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            ai_data = response.json()
            message_content = ai_data.get('choices', [{}])[0].get('message', {}).get('content', '')
            parsed_json = json.loads(message_content)
        except requests.exceptions.RequestException as e:
            error_details = e.response.text if hasattr(e, 'response') and e.response is not None else str(e)
            raise UserError(_("Failed to connect to Groq API. Error: %s") % error_details)
        except json.JSONDecodeError:
            raise UserError(_("Groq API did not return valid JSON. Response was: %s") % message_content)

        # Validate required data presence
        required_keys = ["Weight", "Dimensions", "Origin", "Destination", "Freight Class"]
        if not all(key in parsed_json for key in required_keys):
            raise UserError(
                _("Groq API failed to find required LTL data.\n"
                  "Expected keys: %s\n"
                  "Parsed data received:\n%s") % (required_keys, json.dumps(parsed_json, indent=2))
            )

        # 3. Send to Local API (Email2Quote)
        email2quote_api_url = get_biziship_api_url()
        local_api_bol_url = f"{email2quote_api_url.rstrip('/')}/quote/bol"
        email2quote_api_key = get_email2quote_api_key()
        api_key_header = {"X-API-Key": email2quote_api_key}

        # Decode base64 PDF bytes from Odoo
        pdf_bytes = base64.b64decode(self.bol_file)
        file_name = self.file_name or "bol.pdf"

        try:
            # Send BOL PDF
            files = {"file": (file_name, pdf_bytes, "application/pdf")}
            local_response_bol = requests.post(
                local_api_bol_url, 
                headers=api_key_header, 
                files=files, 
                timeout=30
            )
            local_response_bol.raise_for_status()

            # Process JSON response and create quotes
            response_json = local_response_bol.json()
            quotes = response_json.get('quotes', [])
            
            # Check context to see if we were launched from a sale order
            active_id = self.env.context.get('active_id')
            active_model = self.env.context.get('active_model')
            
            if active_id and active_model == 'sale.order':
                # Save the JSON dict string directly to the sales order
                extracted_details = response_json.get('extracted_details', parsed_json)
                sale_order_record = self.env['sale.order'].browse(active_id)
                sale_order_record.write({'biziship_extracted_json': json.dumps(extracted_details)})

                for q in quotes:
                    delivery_date_raw = q.get('delivery_date')
                    if delivery_date_raw and 'T' in delivery_date_raw:
                        delivery_date_raw = delivery_date_raw.replace('T', ' ')[:19]

                    # Parse charges array into text
                    charges = q.get('charges', [])
                    details_lines = []
                    for c in charges:
                        c_code = c.get('code') or ''
                        c_desc = c.get('description') or ''
                        c_amount = c.get('amount')
                        if c_amount is None:
                            c_amount = 0.0
                        
                        # Format string to align description and amount
                        # Example: Gross Freight Charge                $3,187.72
                        format_str = f"{str(c_desc):<40} ${c_amount:,.2f}"
                        details_lines.append(format_str)
                    
                    details_text = "\n".join(details_lines) if details_lines else "No detailed charges provided."

                    self.env['biziship.quote'].sudo().create({
                        'sale_order_id': active_id,
                        'carrier_name': q.get('carrier_name'),
                        'carrier_code': q.get('carrier_code'),
                        'service_level': q.get('service_level'),
                        'transit_days': q.get('transit_days'),
                        'delivery_date': delivery_date_raw,
                        'total_charge': q.get('total_charge'),
                        'currency': q.get('currency', 'USD'),
                        'quote_id_ref': q.get('quote_id'),
                        'quote_details': details_text,
                    })

        except requests.exceptions.RequestException as e:
            error_details = e.response.text if hasattr(e, 'response') and e.response is not None else str(e)
            raise UserError(
                _("BiziShip External API Blocked: Failed to send data to local Email2Quote API.\n\n"
                  "Please ensure the local service is running and accepting requests.\n\n"
                  "Details:\n%s") % error_details
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
