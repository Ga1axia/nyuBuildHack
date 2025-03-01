import pandas as pd
import anthropic
import json
from datetime import datetime
from flask import Flask, request, render_template, jsonify, redirect, url_for
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['ALLOWED_EXTENSIONS'] = {'csv'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

class ClaudeAnalyzer:
    def __init__(self, api_key):
        self.api_key = api_key
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-3-haiku-20240307"  # Using a faster model for responsiveness

    def analyze_expenses(self, transactions_df):
        """
        Make a single API call to categorize all expenses at once
        """
        # Convert dataframe to string for API request
        transactions_str = transactions_df.to_csv(index=False)
        
        # Define expense categories and subcategories for context
        expense_categories = {
            'Housing': ['Rent/Mortgage', 'Utilities', 'Property Tax', 'Home Insurance', 'Maintenance', 'Furniture/Decor'],
            'Transportation': ['Car Payment', 'Car Insurance', 'Fuel', 'Public Transit', 'Ride Services', 'Maintenance', 'Parking'],
            'Food': ['Groceries', 'Restaurants', 'Food Delivery', 'Coffee Shops', 'Alcohol/Bars'],
            'Healthcare': ['Insurance Premium', 'Medications', 'Doctor Visits', 'Dental Care', 'Vision Care', 'Fitness'],
            'Financial': ['Investments', 'Debt Payments', 'Banking Fees', 'Tax Preparation', 'Overdraft Fees'],
            'Discretionary': ['Entertainment', 'Shopping', 'Travel', 'Subscriptions', 'Hobbies', 'Gifts'],
            'Other': ['Education', 'Childcare', 'Pet Expenses', 'Charitable Giving', 'Miscellaneous'],
            'Income': ['Salary', 'Transfers', 'Gifts', 'Reimbursements', 'Interest']
        }
        
        # Create the prompt for Claude
        prompt = f"""
        Here is a bank transaction history:
        
        {transactions_str}
        
        Please categorize each transaction according to these categories and subcategories:
        {json.dumps(expense_categories, indent=2)}
        
        For transactions that appear to be income (deposits), use the Income category.
        
        Return your analysis as a JSON string with this structure:
        {{
            "categorized_transactions": [
                {{
                    "date": "transaction date",
                    "description": "transaction description",
                    "amount": transaction amount,
                    "category": "main category",
                    "subcategory": "subcategory"
                }},
                // more transactions...
            ]
        }}
        
        Only return valid JSON, no additional text.
        """
        
        # Make the API call
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extract and parse the JSON response
        response_text = response.content[0].text
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Handle invalid JSON by extracting JSON portion
            import re
            json_match = re.search(r'({.*})', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            return {"error": "Failed to parse response", "raw_response": response_text}

    def analyze_savings(self, categorized_data):
        """
        Make a single API call to get savings recommendations based on categorized data
        """
        # Create a summary of spending by category
        category_summary = {}
        for item in categorized_data["categorized_transactions"]:
            category = item["category"]
            amount = item["amount"]
            
            # Skip income transactions for spending analysis
            if category == "Income" or amount > 0:
                continue
                
            if category not in category_summary:
                category_summary[category] = 0
            category_summary[category] += abs(amount)
        
        # Prepare data for the prompt
        transactions_summary = json.dumps(categorized_data["categorized_transactions"], indent=2)
        spending_summary = json.dumps(category_summary, indent=2)
        
        prompt = f"""
        I need your help analyzing spending patterns and identifying savings opportunities.
        
        Here are categorized transactions:
        {transactions_summary}
        
        And here's a summary of spending by category:
        {spending_summary}
        
        Please analyze this data and provide:
        1. The top 3-5 potential areas for savings
        2. For each area, estimate how much could be saved monthly
        3. Specific actionable recommendations for each area
        4. The total estimated monthly savings if all recommendations are followed
        
        Return your analysis as a JSON string with this structure:
        {{
            "savings_areas": [
                {{
                    "area": "name of spending area",
                    "monthly_potential": dollar amount as number,
                    "recommendations": ["specific recommendation 1", "specific recommendation 2"]
                }},
                // more areas...
            ],
            "total_monthly_savings": total dollar amount as number,
            "summary": "brief overall summary of findings"
        }}
        
        Only return valid JSON, no additional text.
        """
        
        # Make the API call
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extract and parse the JSON response
        response_text = response.content[0].text
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Handle invalid JSON by extracting JSON portion
            import re
            json_match = re.search(r'({.*})', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            return {"error": "Failed to parse response", "raw_response": response_text}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    # Check if API key is provided
    api_key = request.form.get('api_key')
    if not api_key:
        return jsonify({"error": "API key is required"}), 400
    
    # Check if file is provided
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file and allowed_file(file.filename):
        # Save the file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # Process CSV file based on column format
            df = pd.read_csv(filepath)
            
            # Basic validation
            required_cols = ['Date', 'Description', 'Amount']
            if not all(col in df.columns for col in required_cols):
                return jsonify({"error": "CSV file must contain Date, Description, and Amount columns"}), 400
            
            # Initialize the Claude Analyzer
            analyzer = ClaudeAnalyzer(api_key)
            
            # Get categorized transactions
            categorized_data = analyzer.analyze_expenses(df)
            
            # Get savings analysis
            savings_analysis = analyzer.analyze_savings(categorized_data)
            
            # Combine results
            result = {
                "categorized_data": categorized_data,
                "savings_analysis": savings_analysis
            }
            
            return jsonify(result)
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"error": "File type not allowed"}), 400

if __name__ == '__main__':
    app.run(debug=True)