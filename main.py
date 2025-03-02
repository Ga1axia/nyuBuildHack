import pandas as pd
import anthropic
import json
from datetime import datetime
from flask import Flask, request, render_template, jsonify, redirect, url_for, session
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from database import db, User, Transaction, Analysis, init_db

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['ALLOWED_EXTENSIONS'] = {'csv'}
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expense_analyzer.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.urandom(24)  # For session management
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database
init_db(app)

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

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400
        
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 400
        
    user = User(
        email=email,
        password_hash=generate_password_hash(password)
    )
    db.session.add(user)
    db.session.commit()
    
    return jsonify({"message": "Registration successful"}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid email or password"}), 401
        
    session['user_id'] = user.id
    return jsonify({"message": "Login successful"}), 200

@app.route('/upload', methods=['POST'])
def upload_file():
    # Check if user is logged in
    if 'user_id' not in session:
        return jsonify({"error": "Please log in first"}), 401
    
    # Get current user
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({"error": "User not found"}), 404
    
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
            
            # Initialize the Claude Analyzer
            analyzer = ClaudeAnalyzer(api_key)
            
            # Get categorized transactions
            categorized_data = analyzer.analyze_expenses(df)
            
            # Store transactions in database
            for transaction in categorized_data['categorized_transactions']:
                # Try different date formats
                date_str = transaction['date']
                parsed_date = None
                date_formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y']
                
                for date_format in date_formats:
                    try:
                        parsed_date = datetime.strptime(date_str, date_format)
                        break
                    except ValueError:
                        continue
                
                if parsed_date is None:
                    return jsonify({"error": f"Unable to parse date format: {date_str}"}), 400
                
                db_transaction = Transaction(
                    user_id=user.id,
                    date=parsed_date,
                    description=transaction['description'],
                    amount=transaction['amount'],
                    category=transaction['category'],
                    subcategory=transaction.get('subcategory')
                )
                db.session.add(db_transaction)
            
            # Get savings analysis
            savings_analysis = analyzer.analyze_savings(categorized_data, savings_level)
            
            # Store analysis in database
            analysis = Analysis(
                user_id=user.id,
                savings_level=savings_level,
                total_monthly_savings=savings_analysis.get('total_monthly_savings'),
                analysis_data=savings_analysis
            )
            db.session.add(analysis)
            db.session.commit()
            
            # Clean up the uploaded file
            os.remove(filepath)
            
            return jsonify({
                "categorized_data": categorized_data,
                "savings_analysis": savings_analysis
            })
            
        except Exception as e:
            # Clean up the uploaded file in case of error
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({"error": str(e)}), 500
            
    return jsonify({"error": "Invalid file type"}), 400

@app.route('/history', methods=['GET'])
def get_history():
    if 'user_id' not in session:
        return jsonify({"error": "Please log in first"}), 401
        
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    # Get user's transaction history
    transactions = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.date.desc()).all()
    
    # Get user's analysis history
    analyses = Analysis.query.filter_by(user_id=user.id).order_by(Analysis.created_at.desc()).all()
    
    return jsonify({
        "transactions": [{
            "date": t.date.strftime('%Y-%m-%d'),
            "description": t.description,
            "amount": t.amount,
            "category": t.category,
            "subcategory": t.subcategory
        } for t in transactions],
        "analyses": [{
            "date": a.created_at.strftime('%Y-%m-%d'),
            "savings_level": a.savings_level,
            "total_monthly_savings": a.total_monthly_savings,
            "analysis_data": a.analysis_data
        } for a in analyses]
    })

if __name__ == '__main__':
    app.run(debug=True)