import smtplib
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import logging
import sqlite3
import time
import os

# Initialize logging for errors
logging.basicConfig(filename="email_errors.log", level=logging.ERROR,
                    format="%(asctime)s - %(levelname)s - %(message)s")

# SMTP credentials for multiple domain emails
smtp_server = "smtp.hostinger.com"
smtp_port = 465  # SSL port
smtp_emails = [
    {"user": "marketing@geartektools.com", "password": "Geartek@123"},
    {"user": "assistance@geartektools.com", "password": "Geartek@123"},
    {"user": "admin@geartektools.com", "password": "sMbm5152@mona"},
    {"user": "information@geartektools.com", "password": "sMbm5152@mona"},
    {"user": "support@geartektools.com", "password": "gearTek@1234"},
    {"user": "contact@geartektools.com", "password": "gearTek@12345"},
    {"user": "info@geartektools.com", "password": "Geartek@123"},
    {"user": "team@geartektools.com", "password": "Geartek@123"},
]

# Database connection for metrics
def log_email_status(recipient, status):
    conn = sqlite3.connect('email_data.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO email_metrics (recipient, status) VALUES (?, ?)", (recipient, status))
    conn.commit()
    conn.close()

def check_email_sent(recipient):
    conn = sqlite3.connect('email_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM email_metrics WHERE recipient = ? AND status = 'sent'", (recipient,))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0  # Return True if the email has already been sent

def send_email(to_email, company_name, subject, body, image_path, smtp_info):
    tracking_url = f"http://127.0.0.1:5000/track_open?email={to_email}"

    # Modify body to include the tracking URL
    body += f'<img src="{tracking_url}" width="1" height="1" alt="" style="display: none;">'

    # Create message container
    msg = MIMEMultipart()
    msg['From'] = smtp_info["user"]
    msg['To'] = to_email
    msg['Subject'] = subject

    # Attach the body to the email
    msg.attach(MIMEText(body, 'html'))

    # Attach product image
    try:
        with open(image_path, 'rb') as img:
            img_data = MIMEImage(img.read())
            img_data.add_header('Content-ID', '<product_image>')
            msg.attach(img_data)
            # Include the product image in the email body with specified width and height
            body += f'<br><br><img src="cid:product_image" width="300" height="420" alt="Product Image">'
            msg.attach(MIMEText(body, 'html'))  # Reattach modified body

    except FileNotFoundError:
        logging.error(f"Product image not found for email to {to_email}")
        log_email_status(to_email, 'bounced')  # Log as bounced if image not found
        return False

    # Attempt to send the email
    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(smtp_info["user"], smtp_info["password"])
            server.sendmail(smtp_info["user"], to_email, msg.as_string())
        print(f"Email sent to {to_email} from {smtp_info['user']}")
        log_email_status(to_email, 'sent')  # Log successful send
        return True
    except Exception as e:
        logging.error(f"Failed to send email to {to_email}: {e}")
        log_email_status(to_email, 'bounced')  # Log as bounced if error occurs
        return False

if __name__ == "__main__":
    pass  # This module can be imported without running
