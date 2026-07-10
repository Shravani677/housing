# Mahindra Gardens - Resident Portal

A premium, modern Single Page Application (SPA) designed for the residents of Mahindra Gardens. The portal allows residents to stay updated with society notices, manage help desk tickets, view upcoming events, and seamlessly track maintenance payments.

## ✨ Features

- **Resident Dashboard:** A comprehensive overview of notices, complaints, and maintenance dues at a glance.
- **Notice Board:** Categorized announcements (Urgent, Maintenance, General) with search and filtering capabilities.
- **Help Desk (Complaints):** Raise new tickets, track the status (Open, In Progress, Resolved) of ongoing issues, and prioritize urgent requests.
- **Maintenance & Billing:** Track pending maintenance dues, view payment history, and generate detailed PDF invoices/receipts.
- **Premium UI:** Dribbble-inspired modern design featuring glassmorphism, smooth micro-animations, skeleton loaders, and contextual toast notifications.
- **Dark Mode:** A sleek, fully persistent Dark Mode theme with automatic preference saving.
- **Responsive Design:** A completely mobile-friendly interface with a collapsible, smooth-transitioning sidebar.

## 🛠️ Technology Stack

- **Frontend:** HTML5, CSS3 (Vanilla), JavaScript (ES6)
- **Design System:** Custom CSS variables for theming, Feather Icons, Google 'Outfit' typography
- **Backend:** Python (Flask)
- **Database:** Local JSON-based storage (for prototyping/portability) with Firebase Auth hooks.
- **Architecture:** Client-side SPA utilizing `fetch` API against REST endpoints.

## 🚀 Getting Started

### Prerequisites
- Python 3.x installed on your system.
- `pip` for installing Python packages.

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Shravani677/housing.git
   cd housing
   ```

2. **Install dependencies:**
   ```bash
   pip install flask flask-cors requests
   ```

3. **Run the server:**
   ```bash
   python server.py
   ```
   The server will start at `http://127.0.0.1:5000`.

4. **Access the Application:**
   Open your browser and navigate to `http://localhost:5000`. 
   
## 📁 Project Structure

```
housing/
├── data/                  # Local JSON databases (users, notices, complaints, etc.)
├── static/                # Static assets
│   ├── css/               # Core styling (style.css)
│   ├── js/                # Application logic (app.js)
│   └── images/            # Backgrounds and logos
├── templates/             # HTML files
│   ├── dashboard.html     # Main SPA Shell
│   └── login.html         # Authentication page
├── server.py              # Flask backend server & REST API routes
└── README.md              # Project documentation
```

## 🎨 UI/UX Highlights
- No page reloads—tab switching happens seamlessly via DOM manipulation.
- Empty states are handled gracefully with illustrations and clear copy.
- API interactions simulate real-world latency using loading skeletons.
- All interactions provide immediate visual feedback (hover states, active states, toasts).

## 🔒 Security Note
This project uses simulated local data storage for ease of setup. Ensure proper environment variables and secured databases are configured before deploying to production.

---
*Built with ❤️ for Mahindra Gardens.*
