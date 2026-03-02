# 🏢 Real Estate Management – Odoo 18

A custom **Real Estate Management system** built on **Odoo 18**, designed to manage properties, offers, property types, tags, users, and **automated customer invoicing for sold properties** using Odoo Accounting.

This project follows Odoo best practices for **modular design, security, scalability, and accounting integration.**


### 📌 Project Overview

This project is split into **two Odoo modules:**

estate :
    Core real estate functionality (properties, offers, tags, types, users)

estate_account :
    Accounting integration – creates and manages invoices for sold properties


## 🧩 Modules Description

### 1️⃣ estate – Real Estate Core Module

Handles all **business logic related to properties.**

### Key Features

- Property management (create, update, sell, cancel)

- Property offers with validations

- Property types & tags

- User extensions

- Menu & UI views

- Security rules


## 📂 Folder Structure
```bash
estate/
├── models/
│ ├── estate_property.py
│ ├── estate_property_offer.py
│ ├── estate_property_tag.py
│ ├── estate_property_type.py
│ └── res_users.py
│
├── views/
│ ├── estate_menus.xml
│ ├── estate_property_views.xml
│ ├── estate_property_offer_views.xml
│ ├── estate_property_tag_views.xml
│ ├── estate_property_type_views.xml
│ └── res_users_views.xml
│
├── security/
│ └── ir.model.access.csv
│
├── init.py
└── manifest.py
```

### 2️⃣ estate_account – Accounting Integration Module

Extends the **estate module** and integrates it with **Odoo Accounting.**

### Key Features

- Automatically creates customer invoices when a property is sold

- Links invoices to properties

- Displays invoices inside the property form (Notebook tab)

- Uses standard account.move model

- Secure access via ACLs


## Folder Structure

```bash
estate_account/
├── models/
│   ├── account_move.py
│   └── estate_property.py
│
├── views/
│   └── estate_property_invoice_page.xml
│
├── security/
│   └── ir.model.access.csv
│
├── __init__.py
└── __manifest__.py
```

## 🔗 Module Dependencies

estate_account depends on :
- estate
- account

Make sure **Accounting** is installed before installing estate_account.

## 🧠 Business Logic Summary

### Property Lifecycle

- Draft → Offer Received → Offer Accepted → **Sold**
- When a property is marked as **Sold**:
  - A **Customer Invoice** is automatically created
  - Invoice includes:
    - Property Selling Price
    - Commission
    - Administrative Fees
  - Invoice is linked to the property


## 🔐 Security & Access Control

- Proper ir.model.access.csv files for both modules
- Only authorized users can :
  - Create / edit properties
  - Accept offers
  - View and manage invoices
- Uses Odoo’s standard security groups


## 🖥 UI & Views

- Clean form & tree views
- Notebook tabs for logical separation
- Invoices shown **inside Property form**
- No popup (target="new") – invoices open in **full page view**
- Fully compatible with **Odoo 18 view rules**


## ⚙️ Installation Steps

1. Clone the repository into your Odoo addons path :
```bash
git clone https://github.com/Pathan-Zuhair/estate-odoo-addons.git
```
2. Update addons path in your Odoo config (if needed)
3. Restart Odoo server
4. Activate Developer Mode
5. Install modules in this order :
   - estate
   - estate_account

## 🧪 Tested On

- Odoo **18.0**
- PostgreSQL 14+
- macOS / Linux
- Python 3.10+


## 🚀 Future Enhancements

- Multi-company support
- Vendor bills for expenses
- Payment tracking
- Property documents management
- Reporting & dashboards


## 👤 Author

### Zuhair Pathan
Odoo Developer

GitHub: https://github.com/Pathan-Zuhair


## 📄 License

This project is licensed under the **LGPL-3 License**, same as Odoo.