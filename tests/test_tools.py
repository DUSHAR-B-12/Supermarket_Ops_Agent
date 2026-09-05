import pytest
from app.db.seed import seed_database
from app.tools.inventory_tools import (
    search_products, get_product, add_product, receive_stock, get_stock, get_low_stock
)
from app.tools.billing_tools import (
    create_draft_bill, add_bill_item, calculate_bill, finalize_bill, get_bill
)
from app.tools.khata_tools import (
    get_customer, get_khata_balance, record_khata_credit, record_khata_repayment
)
from app.tools.preference_tools import (
    get_preference, set_preference
)

def test_inventory_tools(db_session):
    seed_database(db_session)
    results = search_products(db_session, "Maggi")
    assert len(results) >= 1
    maggi_id = results[0]["id"]

    prod = get_product(db_session, str(maggi_id))
    assert prod is not None
    assert prod["name"] == "Maggi 70g"

    rec = receive_stock(db_session, maggi_id, 10.0, reference="Tool Test Stock")
    assert rec["new_quantity"] == 110.0

    st = get_stock(db_session, maggi_id)
    assert st["quantity"] == 110.0

    low = get_low_stock(db_session)
    assert isinstance(low, list)

def test_billing_tools(db_session):
    seed_database(db_session)
    p_info = get_product(db_session, "SKU-ATTA-5KG")
    assert p_info is not None

    b_draft = create_draft_bill(db_session)
    bill_id = b_draft["bill_id"]

    add_res = add_bill_item(db_session, bill_id, p_info["id"], 2.0)
    assert add_res["item_count"] == 1

    calc = calculate_bill(db_session, bill_id)
    assert calc["grand_total"] == 504.0  # (240 * 2) * 1.05 = 504.0

    fin = finalize_bill(db_session, bill_id, payment_method="Cash")
    assert fin["status"] == "finalized"

def test_khata_tools(db_session):
    cust = get_customer(db_session, name="Mahesh", telegram_user_id=999)
    assert cust is not None
    cust_id = cust["id"]

    cred = record_khata_credit(db_session, cust_id, 350.0)
    assert cred["new_credit_balance"] == 350.0

    bal = get_khata_balance(db_session, cust_id)
    assert bal["credit_balance"] == 350.0

    rep = record_khata_repayment(db_session, cust_id, 150.0)
    assert rep["new_credit_balance"] == 200.0

def test_preference_tools(db_session):
    set_res = set_preference(db_session, "user100", "shop_name", "Gupta Kirana Store")
    assert set_res["value"] == "Gupta Kirana Store"

    get_res = get_preference(db_session, "user100", "shop_name")
    assert get_res["value"] == "Gupta Kirana Store"
