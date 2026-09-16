import pandas as pd

orders = pd.read_csv("data/orders.csv")
finance = pd.read_csv("data/finance_export.csv")

print("=== ROW COUNTS ===")
print(f"Orders: {len(orders)}")
print(f"Finance: {len(finance)}")

print("\n=== ORDER CHANNELS ===")
print(orders["channel"].value_counts())

print("\n=== FINANCE CHANNELS ===")
print(finance["channel"].value_counts())

print("\n=== CURRENCIES ===")
print(orders["currency"].value_counts())

print("\n=== STATUSES ===")
print(orders["status"].value_counts())

print("\n=== TEST ORDERS ===")
print(orders["is_test_order"].value_counts())

print("\n=== REFUNDS ===")
print(f"Orders with refunds: {(orders['refund'] > 0).sum()}")

print("\n=== DUPLICATES ===")
print(f"Exact duplicate rows: {orders.duplicated().sum()}")
print(f"Rows: {len(orders)}")
print(f"Unique order IDs: {orders['order_id'].nunique()}")