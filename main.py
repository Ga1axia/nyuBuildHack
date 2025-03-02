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
        self.api_key = api_key.split()[0]
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

    def analyze_savings(self, categorized_data, savings_level="Low"):
        """
        Make a single API call to get savings recommendations based on categorized data and savings level
        """
        
        print(categorized_data)
        
        # Extract unique categories from the categorized data
        unique_categories = set(item["category"] for item in categorized_data["categorized_transactions"])
        
        category_sums = {}
        
        for category in unique_categories:
            category_sums[category] = 0
            for item in categorized_data["categorized_transactions"]:
                if item["category"] == category:
                    if item["amount"] < 0:
                        category_sums[category] += abs(item["amount"])
                    
        print(category_sums)
        
        # Order category sums from high to low
        ordered_category_sums = dict(sorted(category_sums.items(), key=lambda item: item[1], reverse=True))
        
        # Calculate savings factor based on selected level
        savings_factor = {
            "Low": 0.05,      # 5% savings target
            "Medium": 0.15,   # 15% savings target
            "High": 0.25      # 25% savings target
        }.get(savings_level, 0.05)  # Default to Low if not specified
        
        # Prepare data for the prompt
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
        
        transactions_summary = json.dumps(categorized_data["categorized_transactions"], indent=2)
        spending_summary = json.dumps(category_summary, indent=2)
        
        prompt = f"""
        I need your help analyzing spending patterns and identifying savings opportunities.
        
        Here are categorized transactions:
        {transactions_summary}
        
        And here's a summary of spending by category:
        {spending_summary}
        
        And here's the total spending by category:
        {json.dumps(ordered_category_sums, indent=2)}
        
        The user has selected a "{savings_level}" savings level, which indicates they want 
        {'modest savings with minimal lifestyle changes' if savings_level == 'Low' else 'balanced approach with moderate changes' if savings_level == 'Medium' else 'aggressive savings with significant adjustments'}.
        
        Based on this level, aim for approximately {int(savings_factor * 100)}% in savings for their main spending categories.
        
        Please analyze this data and provide:
        1. The most significant areas of spending (top 3-5 categories)
        2. For each area, calculate the current monthly spending and a realistic target amount after savings
        3. Calculate how much could be saved monthly based on the {savings_level} savings level
        4. Specific actionable recommendations for each area to reduce spending. When recommending, reference the original transactions and how they might be changed. Be specific.
        5. The total estimated monthly savings if all recommendations are followed 
        
        Return your analysis as a JSON string with this structure:
        {{
            "savings_areas": [
                {{
                    "area": "name of spending area",
                    "current_spending": current monthly spending as number directly from the ordered category sums,
                    "monthly_potential": realistic monthly savings as number,
                    "recommendations": ["specific recommendation 1", "specific recommendation 2"]
                }},
                // more areas...
            ],
            "total_monthly_savings": total dollar amount as number,
            "savings_level": "{savings_level}",
            "summary": "brief overall summary of findings"
        }}
        
        IMPORTANT: All numerical values for current spending and potential savings must be based on the actual transaction data provided, not hypothetical amounts.
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
    api_key = api_key.split()[0]
    if not api_key:
        return jsonify({"error": "API key is required"}), 400
    
    # Check if savings level is provided
    savings_level = request.form.get('savings_level', 'Low')
    if savings_level not in ['Low', 'Medium', 'High']:
        savings_level = 'Low'  # Default to Low if invalid value
    
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
            
            print(api_key)
            
            # Initialize the Claude Analyzer
            analyzer = ClaudeAnalyzer(api_key)
            
            # Get categorized transactions
            categorized_data = analyzer.analyze_expenses(df)
            
            # Get savings analysis with the specified savings level
            savings_analysis = analyzer.analyze_savings(categorized_data, savings_level)
            
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