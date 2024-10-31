from flask import Flask, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_executor import Executor
from flask_migrate import Migrate
import os
import sqlite3
import logging
import csv
from email_sender import send_email, smtp_emails
import time

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///email_data.db'  
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

from models import db, Campaign, EmailLog

db.init_app(app)
migrate = Migrate(app, db)

executor = Executor(app)

# Logging configuration
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()])

# Database initialization (run once to create table)
def init_db():
    conn = sqlite3.connect('email_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS email_metrics (
                        id INTEGER PRIMARY KEY,
                        recipient TEXT,
                        status TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )''')
    conn.commit()
    conn.close()

# Initialize the database when the app starts
init_db()  # Run once to set up the database

# Fetch metrics for the dashboard
def fetch_metrics():
    conn = sqlite3.connect('email_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM email_metrics WHERE status='sent'")
    sent_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM email_metrics WHERE status='opened'")
    opened_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM email_metrics WHERE status='replied'")
    replied_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM email_metrics WHERE status='bounced'")
    bounced_count = cursor.fetchone()[0]
    
    conn.close()
    return {
        "sent": sent_count,
        "opened": opened_count,
        "replied": replied_count,
        "bounced": bounced_count
    }

@app.route('/')
def dashboard():
    metrics = fetch_metrics()
    return render_template('dashboard.html', metrics=metrics)

@app.route('/manage-campaign', methods=['GET', 'POST'])
def manage_campaign():
    if request.method == 'POST':
        campaign_name = request.form['campaign_name']
        csv_file = request.files['csv_file']
        subject_template = request.form['subject']
        body_template = request.form['body']
        image_file = request.files['image_file']
        
        # Create uploads directory if it doesn't exist
        uploads_dir = 'uploads'
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir)

        csv_file_path = os.path.join(uploads_dir, csv_file.filename)
        image_path = os.path.join(uploads_dir, image_file.filename)  # Save image as needed
        csv_file.save(csv_file_path)
        image_file.save(image_path)  # Save the uploaded image

        # Create and save the campaign
        new_campaign = Campaign(name=campaign_name, csv_file_path=csv_file_path, subject=subject_template, body=body_template)  # Use csv_file_path here
        db.session.add(new_campaign)
        db.session.commit()

        # Start sending emails in a background thread for the new campaign
        executor.submit(send_emails_for_campaign, new_campaign.id, csv_file_path, image_path)
        logging.info(f"Email sending process started for campaign: {campaign_name}")
        
        return redirect(url_for('dashboard'))

    return render_template('manage_campaign.html')


@app.route('/campaign-performance/<int:campaign_id>')
def campaign_performance(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)  # Fetch the specific campaign
    metrics = fetch_campaign_metrics(campaign_id)  # Create a function to fetch campaign metrics
    return render_template('campaign_performance.html', campaign=campaign, metrics=metrics)

def fetch_campaign_metrics(campaign_id):
    conn = sqlite3.connect('email_data.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM email_metrics WHERE campaign_id = ? AND status='sent'", (campaign_id,))
    sent_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM email_metrics WHERE campaign_id = ? AND status='opened'", (campaign_id,))
    opened_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM email_metrics WHERE campaign_id = ? AND status='replied'", (campaign_id,))
    replied_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM email_metrics WHERE campaign_id = ? AND status='bounced'", (campaign_id,))
    bounced_count = cursor.fetchone()[0]
    
    conn.close()
    return {
        "sent": sent_count,
        "opened": opened_count,
        "replied": replied_count,
        "bounced": bounced_count
    }


def send_emails_for_campaign(campaign_id, csv_file_path, image_path):
    campaign = Campaign.query.get(campaign_id)
    smtp_count = len(smtp_emails)

    with open(csv_file_path, 'r') as csv_file:
        reader = csv.DictReader(csv_file)
        for index, row in enumerate(reader):
            recipient = row.get('EMAIL')
            company_name = row.get('COMPANY_NAME')  # Ensure this matches your CSV column for company names

            if not recipient:  # Check if recipient email is missing
                logging.error("Recipient email is missing in the CSV. Skipping this entry.")
                continue

            # Check if the email has already been sent
            if EmailLog.query.filter_by(campaign_id=campaign_id, recipient=recipient, status='sent').count() > 0:
                logging.info(f"Email to {recipient} has already been sent. Skipping.")
                continue

            smtp_info = smtp_emails[index % smtp_count]

            # Dynamically format subject and body to replace {{COMPANY_NAME}}
            subject = campaign.subject.replace("{{COMPANY_NAME}}", company_name)
            body = campaign.body.replace("{{COMPANY_NAME}}", company_name)

            # Send the email with formatted subject and body
            success = send_email(recipient, company_name, subject, body, image_path, smtp_info)
            if success:
                log = EmailLog(campaign_id=campaign_id, recipient=recipient, status='sent')
                db.session.add(log)
                db.session.commit()

            # Add a delay of 2 seconds after each email to avoid triggering spam filters
            time.sleep(2)

            # After every 8 emails, wait 5 minutes before continuing
            if (index + 1) % 8 == 0:
                logging.info("Cycle of 8 emails completed, waiting for 5 minutes.")
                print("Cycle of 8 emails completed, waiting for 5 minutes.")
                time.sleep(300)  # 5-minute delay

    logging.info("All Emails Have Been Sent Successfully for campaign: " + campaign.name)


@app.route('/track_open')
def track_open():
    email = request.args.get('email')
    if email:
        logging.info(f'Track open event for email: {email}')
        log_email_open(email)
    else:
        logging.warning('Track open called without an email parameter.')
    return '', 204  # Return a no content response

def log_email_open(email):
    connection = sqlite3.connect('email_data.db')
    cursor = connection.cursor()
    try:
        cursor.execute('''INSERT INTO email_metrics (recipient, status)
                          VALUES (?, 'opened')
                          ON CONFLICT(recipient) DO UPDATE SET status='opened', timestamp=CURRENT_TIMESTAMP''',
                       (email,))
        connection.commit()
    except Exception as e:
        logging.error(f"Error logging email open: {e}")
    finally:
        cursor.close()
        connection.close()

if __name__ == "__main__":
    app.run(debug=True)
