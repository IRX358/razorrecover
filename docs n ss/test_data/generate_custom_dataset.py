import csv
import random
from datetime import datetime, timedelta
import uuid
import os

# Configuration
NUM_TRANSACTIONS = 500
OUTPUT_FILE = 'custom_transactions.csv'
COLUMNS = ['payment_id', 'order_id', 'amount', 'status', 'captured', 'method', 'bank', 'error_source', 'error_step', 'error_reason', 'created_at']

# Helpers
methods = ['upi', 'card', 'netbanking']
banks = ['HDFC', 'SBI', 'ICICI', 'AXIS']
random_noise_reasons = ['user_cancelled', 'insufficient_funds', 'invalid_vpa', 'payment_failed']

def random_date(start, end):
    return start + timedelta(seconds=random.randint(0, int((end - start).total_seconds())))

def generate_row(created_at):
    amount = round(random.uniform(100.0, 15000.0), 2)
    payment_id = f"pay_{uuid.uuid4().hex[:14]}"
    order_id = f"order_{uuid.uuid4().hex[:14]}"
    
    is_success = random.random() < 0.7
    
    if is_success:
        return [
            payment_id, order_id, amount, 'captured', 'True', 
            random.choice(methods), random.choice(banks), 
            '', '', '', created_at.isoformat() + "Z"
        ]
    else:
        # Failure logic
        fail_type = random.random()
        if fail_type < 0.60:
            # 60% UPI Timeout HDFC cluster
            return [
                payment_id, order_id, amount, 'failed', 'False', 
                'upi', 'HDFC', 'bank', 'payment_processing', 'upi_timeout', 
                created_at.isoformat() + "Z"
            ]
        elif fail_type < 0.80:
            # 20% Card Declined Risk cluster
            return [
                payment_id, order_id, amount, 'failed', 'False', 
                'card', '', 'gateway', 'payment_authorization', 'card_declined_risk', 
                created_at.isoformat() + "Z"
            ]
        else:
            # 20% Random noise
            return [
                payment_id, order_id, amount, 'failed', 'False', 
                random.choice(methods), random.choice(banks), 
                random.choice(['customer', 'bank']), 'payment_authorization', 
                random.choice(random_noise_reasons), created_at.isoformat() + "Z"
            ]

def main():
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)

    # Generate sorted sequential dates to simulate real-time flow
    dates = sorted([random_date(start_date, end_date) for _ in range(NUM_TRANSACTIONS)])

    data = []
    for d in dates:
        data.append(generate_row(d))

    # Get the directory of this script so output is saved alongside it
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(current_dir, OUTPUT_FILE)

    # Write CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        writer.writerows(data)

    print(f"Successfully generated {NUM_TRANSACTIONS} simulated transactions.")
    print(f"Output saved to: {output_path}")

if __name__ == '__main__':
    main()
