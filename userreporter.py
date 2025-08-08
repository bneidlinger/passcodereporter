import tkinter as tk
from tkinter import filedialog, messagebox
import base64
import re
from datetime import datetime
import os
import html  # For HTML escaping
import json  # For safe JSON encoding

# Parse Bosch TXT file
def parse_bosch_txt(filepath):
    # Validate file path
    if not os.path.isfile(filepath):
        raise ValueError("Invalid file path")
    
    seen_users = {}  # Track unique users by User ID to avoid duplicates
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip().replace(" ,", ",").replace(", ", ",")
            if line.startswith("User "):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) > 6:
                    # Extract user ID from first part (e.g., "User 0" -> "0")
                    user_id_part = parts[0]  # "User 0"
                    user_id = user_id_part.replace("User ", "")
                    
                    # Fix Bosch's weird spacing in usernames
                    # Remove spaces that appear to be in the middle of words
                    raw_name = parts[1]
                    # Remove spaces between letter characters that appear to be breaking words
                    # Pattern: lowercase letter + space + lowercase letter = remove space
                    # First pass: remove obvious mid-word breaks
                    user_name = re.sub(r'([a-z])\s+([a-z])', r'\1\2', raw_name)
                    # Second pass: remove spaces breaking common patterns like "er" endings
                    user_name = re.sub(r'([a-zA-Z])\s+([a-z]{1,2}\b)', r'\1\2', user_name)
                    # Clean up any remaining multiple spaces
                    user_name = " ".join(user_name.split())
                    # Remove all spaces from passcode
                    passcode = parts[2].replace(" ", "")
                    
                    auth_levels = parts[5:13]  # A1-A8 Auth columns
                    auth_val = None
                    for idx, val in enumerate(auth_levels, start=1):
                        if val != "0" and val.lower() != "no":
                            auth_val = f"A{idx}"
                            break
                    if not auth_val:
                        auth_val = "None"
                    
                    # Filter logic: Skip User* entries that have no passcode (0 or empty)
                    # Keep entry if:
                    # 1. Username is NOT User* pattern, OR
                    # 2. Username IS User* but has a non-zero passcode
                    is_user_star = (user_name.startswith("User ") and 
                                  user_name[5:].replace(" ", "").isdigit())
                    has_passcode = passcode and passcode != "0"
                    
                    if not is_user_star or has_passcode:
                        # Only add if we haven't seen this user ID before (deduplication)
                        if user_id not in seen_users:
                            seen_users[user_id] = [user_name, passcode, auth_val]
    
    # Return the deduplicated data as a list
    return list(seen_users.values())

# Convert image to base64 (without resizing - users should provide appropriately sized images)
def process_logo(image_path):
    """
    Read an image file and convert it to base64.
    Note: Without PIL, we cannot resize images. Users should provide images under 100KB.
    """
    try:
        # Validate file path
        if not os.path.isfile(image_path):
            raise ValueError("Invalid image file path")
            
        with open(image_path, "rb") as image_file:
            img_data = image_file.read()
            
        # Check file size and warn if too large
        file_size = len(img_data)
        if file_size > 100 * 1024:  # 100KB warning threshold
            response = messagebox.askyesno(
                "Large Image Warning",
                f"The logo image is {file_size // 1024}KB. Large images may slow down the report.\n\n"
                "For best performance, use images under 100KB.\n\n"
                "Continue anyway?",
                icon='warning'
            )
            if not response:
                return None
                
        # Determine image type from file extension
        ext = os.path.splitext(image_path)[1].lower()
        mime_types = {'.png': 'png', '.jpg': 'jpeg', '.jpeg': 'jpeg', 
                      '.gif': 'gif', '.webp': 'webp'}
        mime_type = mime_types.get(ext, 'png')  # Default to png if unknown
            
        return base64.b64encode(img_data).decode("utf-8"), mime_type
    except Exception as e:
        messagebox.showerror("Logo Error", f"Failed to process logo: {str(e)}")
        return None

# Generate HTML report
def generate_html(data, password="", logo_data=None):
    # Table rows
    table_rows = ""
    for row in data:
        # Parse auth value - extract number from "A1", "A2", etc., or default to "None"
        auth_value = row[2]
        if auth_value.startswith("A") and len(auth_value) == 2 and auth_value[1].isdigit():
            auth_num = auth_value[1]
        else:
            auth_num = "None"
        
        # Build select options
        auth_options = ['<option value="None"' + (' selected' if auth_num == "None" else '') + '>None</option>']
        for level in range(1, 9):
            selected = ' selected' if str(level) == auth_num else ''
            auth_options.append(f'<option value="A{level}"{selected}>A{level}</option>')
        
        table_rows += f"""
        <tr>
            <td class="editable-cell" contenteditable='true'>{html.escape(row[0])}</td>
            <td class="editable-cell passcode-cell" contenteditable='true'>{html.escape(row[1])}</td>
            <td class="auth-cell">
                <select class="auth-select" onchange="markModified(this)">
                    {''.join(auth_options)}
                </select>
            </td>
            <td class="action-cell">
                <button class="delete-btn" onclick='deleteRow(this)'>Remove</button>
            </td>
        </tr>"""

    # Embed logo HTML if exists
    logo_html = ""
    if logo_data:
        logo_b64, mime_type = logo_data
        # Validate mime type to prevent injection
        if mime_type in ['png', 'jpeg', 'gif', 'webp']:
            logo_html = f"""
    <div class="header-logo">
        <img src='data:image/{mime_type};base64,{logo_b64}' alt="Company Logo">
    </div>"""

    # HTML template
    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Content-Security-Policy" content="default-src 'self' data:; script-src 'unsafe-inline'; style-src 'unsafe-inline';">
<title>Security System Passcode Manager</title>
<style>
* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0a0e27;
    min-height: 100vh;
    color: #64748b;
}}

/* Login Screen */
#loginDiv {{
    background: #ffffff;
    border-radius: 8px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07);
    padding: 48px;
    max-width: 420px;
    margin: 120px auto;
    border: 1px solid #e2e8f0;
}}

.login-header {{
    text-align: center;
    margin-bottom: 32px;
}}

.security-badge {{
    width: 48px;
    height: 48px;
    background: #0f172a;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 16px;
}}

.security-badge::before {{
    content: "";
    width: 24px;
    height: 24px;
    border: 3px solid #3b82f6;
    border-radius: 50%;
    border-top-color: transparent;
}}

#loginDiv h2 {{
    color: #0f172a;
    font-size: 24px;
    font-weight: 600;
    letter-spacing: -0.025em;
}}

.login-subtitle {{
    color: #64748b;
    font-size: 14px;
    margin-top: 8px;
}}

#pwdInput {{
    width: 100%;
    padding: 12px 16px;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    font-size: 15px;
    margin-bottom: 24px;
    transition: all 0.2s;
    background: #f8fafc;
}}

#pwdInput:focus {{
    outline: none;
    border-color: #3b82f6;
    background: #ffffff;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}}

.submit-btn {{
    background: #0f172a;
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 6px;
    font-size: 15px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    width: 100%;
}}

.submit-btn:hover {{
    background: #1e293b;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}}

/* Main Content */
#mainContent {{
    background: #ffffff;
    min-height: 100vh;
    padding: 0;
}}

.app-header {{
    background: #0f172a;
    padding: 24px 32px;
    border-bottom: 1px solid #1e293b;
}}

.header-content {{
    max-width: 1400px;
    margin: 0 auto;
    display: flex;
    justify-content: space-between;
    align-items: center;
}}

.header-left {{
    display: flex;
    align-items: center;
    gap: 24px;
}}

.header-logo img {{
    max-height: 40px;
    height: auto;
}}

.app-title {{
    color: #ffffff;
    font-size: 20px;
    font-weight: 600;
    letter-spacing: -0.025em;
}}

.header-stats {{
    display: flex;
    gap: 32px;
}}

.stat-item {{
    color: #94a3b8;
    font-size: 14px;
}}

.stat-value {{
    color: #ffffff;
    font-weight: 600;
    margin-left: 8px;
}}

.main-container {{
    max-width: 1400px;
    margin: 0 auto;
    padding: 32px;
}}

/* Action Bar */
.action-bar {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}}

.action-buttons {{
    display: flex;
    gap: 12px;
}}

.action-btn {{
    background: #ffffff;
    color: #475569;
    border: 1px solid #e2e8f0;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 8px;
}}

.action-btn:hover {{
    background: #f1f5f9;
    border-color: #cbd5e1;
}}

.action-btn.primary {{
    background: #3b82f6;
    color: white;
    border-color: #3b82f6;
}}

.action-btn.primary:hover {{
    background: #2563eb;
    border-color: #2563eb;
}}

/* Instructions Indicator */
.instructions-indicator {{
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    margin-left: auto;
    margin-right: 16px;
}}

.help-icon {{
    width: 20px;
    height: 20px;
    background: #3b82f6;
    color: white;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: bold;
    cursor: help;
}}

.help-text {{
    color: #64748b;
    font-size: 14px;
    font-weight: 500;
}}

.instructions-tooltip {{
    position: absolute;
    top: 100%;
    right: 0;
    margin-top: 8px;
    background: #0f172a;
    color: white;
    padding: 16px;
    border-radius: 8px;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
    width: 320px;
    z-index: 1000;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.3s, visibility 0.3s;
    font-size: 13px;
    line-height: 1.6;
}}

.instructions-indicator:hover .instructions-tooltip {{
    opacity: 1;
    visibility: visible;
}}

.instructions-tooltip::before {{
    content: "";
    position: absolute;
    bottom: 100%;
    right: 20px;
    border-width: 8px;
    border-style: solid;
    border-color: transparent transparent #0f172a transparent;
}}

.instructions-tooltip h4 {{
    margin: 0 0 12px 0;
    font-size: 14px;
    font-weight: 600;
    color: #f1f5f9;
}}

.instructions-tooltip ul {{
    margin: 0;
    padding-left: 20px;
    list-style: none;
}}

.instructions-tooltip li {{
    margin-bottom: 8px;
    position: relative;
    padding-left: 16px;
}}

.instructions-tooltip li::before {{
    content: "•";
    position: absolute;
    left: 0;
    color: #3b82f6;
}}

/* Table Styles */
.table-container {{
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    overflow: hidden;
}}

table {{
    width: 100%;
    border-collapse: collapse;
}}

thead {{
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
}}

th {{
    padding: 12px 24px;
    text-align: left;
    font-weight: 500;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #64748b;
}}

td {{
    padding: 16px 24px;
    border-bottom: 1px solid #f1f5f9;
    font-size: 14px;
    color: #0f172a;
}}

tr:last-child td {{
    border-bottom: none;
}}

tr:hover {{
    background-color: #f8fafc;
}}

.editable-cell {{
    position: relative;
    cursor: text;
    transition: all 0.2s;
}}

.editable-cell:focus {{
    outline: none;
    background: #f0f9ff;
    box-shadow: inset 0 0 0 2px #3b82f6;
}}

.passcode-cell {{
    font-family: 'Monaco', 'Courier New', monospace;
    letter-spacing: 0.05em;
}}

.auth-cell {{
    font-weight: 500;
    color: #3b82f6;
}}

.auth-select {{
    width: 100%;
    padding: 4px 8px;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    background: white;
    color: #3b82f6;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
}}

.auth-select:focus {{
    outline: none;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}}

.auth-select:hover {{
    border-color: #cbd5e1;
}}

.deleted .auth-select {{
    pointer-events: none;
    opacity: 0.5;
    background: #f8f8f8;
}}

.action-cell {{
    text-align: right;
}}

/* Status Classes */
.modified {{
    background-color: #fef3c7;
}}

.deleted {{
    background-color: #fef2f2;
    position: relative;
}}

.deleted::after {{
    content: "DELETED";
    position: absolute;
    top: 50%;
    right: 150px;
    transform: translateY(-50%);
    background: #dc2626;
    color: white;
    font-size: 10px;
    padding: 2px 8px;
    border-radius: 3px;
    font-weight: 600;
    letter-spacing: 0.05em;
}}

.deleted td {{
    position: relative;
    color: #991b1b;
    opacity: 0.85;
}}

.deleted td::after {{
    content: "";
    position: absolute;
    left: 0;
    top: 50%;
    width: 100%;
    height: 1px;
    background: #dc2626;
    opacity: 0.3;
}}

.deleted .editable-cell {{
    pointer-events: none;
    cursor: not-allowed;
}}

.deleted .delete-btn {{
    background: #059669;
    color: white;
    border-color: #059669;
}}

.deleted .delete-btn:hover {{
    background: #047857;
    border-color: #047857;
}}

.restore-btn {{
    background: #059669 !important;
    color: white !important;
    border-color: #059669 !important;
}}

.restore-btn:hover {{
    background: #047857 !important;
    border-color: #047857 !important;
}}

.added {{
    background-color: #d1fae5;
    animation: fadeIn 0.3s ease;
}}

@keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(-10px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}

/* Delete Button */
.delete-btn {{
    background: transparent;
    color: #ef4444;
    border: 1px solid #fecaca;
    padding: 6px 12px;
    border-radius: 4px;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
    font-weight: 500;
}}

.delete-btn:hover {{
    background: #fef2f2;
    border-color: #ef4444;
}}

/* Pagination */
.pagination {{
    margin-top: 24px;
    display: flex;
    justify-content: center;
    gap: 8px;
    padding-top: 24px;
    border-top: 1px solid #e2e8f0;
}}

.pagination button {{
    min-width: 40px;
    height: 40px;
    padding: 0 12px;
    border: 1px solid #e2e8f0;
    background: white;
    color: #475569;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    transition: all 0.2s;
}}

.pagination button:hover {{
    background: #f8fafc;
    border-color: #cbd5e1;
}}

.pagination button.active {{
    background: #0f172a;
    color: white;
    border-color: #0f172a;
}}

/* Responsive Design */
@media (max-width: 768px) {{
    .main-container {{
        padding: 16px;
    }}
    
    .action-bar {{
        flex-direction: column;
        gap: 16px;
    }}
    
    .action-buttons {{
        width: 100%;
        flex-direction: column;
    }}
    
    .action-btn {{
        width: 100%;
        justify-content: center;
    }}
    
    th, td {{
        padding: 12px;
        font-size: 13px;
    }}
    
    .header-content {{
        flex-direction: column;
        gap: 16px;
        text-align: center;
    }}
}}
</style>
</head>
<body>
<div id="loginDiv">
  <div class="login-header">
    <div class="security-badge"></div>
    <h2>Authentication Required</h2>
    <div class="login-subtitle">Enter your credentials to access the system</div>
  </div>
  <input type="password" id="pwdInput" placeholder="Enter password">
  <button class="submit-btn" onclick="checkPassword()">Authenticate</button>
</div>
<div id="mainContent" style="display:none;">
  <div class="app-header">
    <div class="header-content">
      <div class="header-left">
        {logo_html if logo_data else ''}
        <div class="app-title">Security System Passcode Manager</div>
      </div>
      <div class="header-stats">
        <div class="stat-item">
          Report Generated<span class="stat-value">{datetime.now().strftime('%b %d, %Y')}</span>
        </div>
        <div class="stat-item">
          Total Users<span class="stat-value" id="userCount">{len(data)}</span>
        </div>
      </div>
    </div>
  </div>
  <div class="main-container">
    <div class="action-bar">
      <div class="action-buttons">
        <button class="action-btn primary" onclick="addRow()">Add User</button>
        <button class="action-btn" onclick="exportHTML()">Export Report</button>
      </div>
      <div class="instructions-indicator">
        <span class="help-text">Instructions</span>
        <div class="help-icon">?</div>
        <div class="instructions-tooltip">
          <h4>How to Use This Report</h4>
          <ul>
            <li><strong>Edit Users:</strong> Click any cell to edit directly</li>
            <li><strong>Add Users:</strong> Click "Add User" to create a new entry</li>
            <li><strong>Remove Users:</strong> Click "Remove" to mark for deletion</li>
            <li><strong>Restore Users:</strong> Click "Restore" on deleted entries</li>
            <li><strong>Save Changes:</strong> Click "Export Report" to download with all modifications</li>
          </ul>
          <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #334155; color: #94a3b8; font-size: 12px;">
            <strong>Note:</strong> Changes are only saved when you export the report.
          </div>
        </div>
      </div>
    </div>
    <div class="table-container">
      <table id="dataTable">
        <thead>
          <tr>
            <th>User Name</th>
            <th>Passcode</th>
            <th>Authority Level</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {table_rows}
        </tbody>
      </table>
    </div>
    <div class="pagination" id="pagination"></div>
  </div>
</div>
<script>
let PASSWORD = {json.dumps(password) if password else '""'};
let currentPage = 1;
const rowsPerPage = 50;
const table = document.getElementById("dataTable").getElementsByTagName("tbody")[0];

function checkPassword() {{
  let input = document.getElementById("pwdInput").value;
  if (input === PASSWORD) {{
    document.getElementById("loginDiv").style.display = "none";
    document.getElementById("mainContent").style.display = "block";
    paginateTable();
    updateUserCount();
  }} else {{
    alert("Incorrect password. Please try again.");
    document.getElementById("pwdInput").value = "";
  }}
}}


function updateUserCount() {{
  const allRows = Array.from(table.rows);
  const activeRows = allRows.filter(row => !row.classList.contains("deleted"));
  const deletedRows = allRows.filter(row => row.classList.contains("deleted"));
  
  // Update the count to show active users
  document.getElementById("userCount").textContent = activeRows.length;
  
  // Optionally show deleted count in header
  let deletedInfo = document.getElementById("deletedCount");
  if (!deletedInfo && deletedRows.length > 0) {{
    let statsDiv = document.querySelector(".header-stats");
    let deletedStat = document.createElement("div");
    deletedStat.className = "stat-item";
    deletedStat.innerHTML = `Marked for Deletion<span class="stat-value" id="deletedCount" style="color: #ef4444;">${{deletedRows.length}}</span>`;
    statsDiv.appendChild(deletedStat);
  }} else if (deletedInfo) {{
    if (deletedRows.length > 0) {{
      deletedInfo.textContent = deletedRows.length;
    }} else {{
      deletedInfo.parentElement.remove();
    }}
  }}
}}

function paginateTable() {{
  const rows = Array.from(table.rows); // Include ALL rows, including deleted
  const totalPages = Math.ceil(rows.length / rowsPerPage);
  
  // Hide all rows first
  rows.forEach(row => row.style.display = "none");
  
  // Show rows for current page (including deleted ones)
  const start = (currentPage - 1) * rowsPerPage;
  const end = start + rowsPerPage;
  rows.slice(start, end).forEach(row => row.style.display = "");
  
  // Update pagination buttons
  let pagDiv = document.getElementById("pagination");
  pagDiv.innerHTML = "";
  
  if (totalPages > 1) {{
    for (let i = 1; i <= totalPages; i++) {{
      let btn = document.createElement("button");
      btn.textContent = i;
      if (i === currentPage) btn.classList.add("active");
      btn.onclick = () => {{ 
        currentPage = i; 
        paginateTable(); 
      }};
      pagDiv.appendChild(btn);
    }}
  }}
}}

function deleteRow(btn) {{
  let row = btn.parentNode.parentNode;
  
  if (row.classList.contains("deleted")) {{
    // Restore the row
    row.classList.remove("deleted");
    btn.textContent = "Remove";
    btn.classList.remove("restore-btn");
    
    // Re-enable editing
    let cells = row.querySelectorAll(".editable-cell");
    cells.forEach(cell => {{
      cell.contentEditable = "true";
    }});
    
    // Re-enable auth dropdown
    let authSelect = row.querySelector(".auth-select");
    if (authSelect) {{
      authSelect.disabled = false;
    }}
  }} else {{
    // Mark as deleted
    if (confirm("Mark this user for deletion?")) {{
      row.classList.add("deleted");
      btn.textContent = "Restore";
      btn.classList.add("restore-btn");
      
      // Disable editing on deleted rows
      let cells = row.querySelectorAll(".editable-cell");
      cells.forEach(cell => {{
        cell.contentEditable = "false";
      }});
      
      // Disable auth dropdown
      let authSelect = row.querySelector(".auth-select");
      if (authSelect) {{
        authSelect.disabled = true;
      }}
    }}
  }}
  
  updateUserCount();
  paginateTable();
}}

function markModified(element) {{
  let row = element.closest("tr");
  if (!row.classList.contains("deleted")) {{
    row.classList.add("modified");
  }}
}}

function addRow() {{
  let row = table.insertRow();
  row.classList.add("added");
  
  // Add name cell
  let nameCell = row.insertCell();
  nameCell.classList.add("editable-cell");
  nameCell.contentEditable = "true";
  nameCell.textContent = "";
  nameCell.addEventListener("input", function() {{
    if (!this.parentNode.classList.contains("deleted")) {{
      this.parentNode.classList.add("modified");
    }}
  }});
  
  // Add passcode cell
  let passcodeCell = row.insertCell();
  passcodeCell.classList.add("editable-cell", "passcode-cell");
  passcodeCell.contentEditable = "true";
  passcodeCell.textContent = "";
  passcodeCell.addEventListener("input", function() {{
    if (!this.parentNode.classList.contains("deleted")) {{
      this.parentNode.classList.add("modified");
    }}
  }});
  
  // Add authority cell with dropdown
  let authCell = row.insertCell();
  authCell.classList.add("auth-cell");
  let selectHtml = `<select class="auth-select" onchange="markModified(this)">
    <option value="None" selected>None</option>`;
  for (let level = 1; level <= 8; level++) {{
    selectHtml += `<option value="A${{level}}">A${{level}}</option>`;
  }}
  selectHtml += `</select>`;
  authCell.innerHTML = selectHtml;
  
  // Add action cell
  let actionCell = row.insertCell();
  actionCell.classList.add("action-cell");
  actionCell.innerHTML = `<button class="delete-btn" onclick='deleteRow(this)'>Remove</button>`;
  
  updateUserCount();
  paginateTable();
  
  // Focus on first cell of new row
  row.cells[0].focus();
}}

// Add event listeners to existing editable cells
document.addEventListener("DOMContentLoaded", function() {{
  document.querySelectorAll(".editable-cell").forEach(cell => {{
    cell.addEventListener("input", function() {{
      if (!this.parentNode.classList.contains("deleted")) {{
        this.parentNode.classList.add("modified");
      }}
    }});
  }});
}});

function exportHTML() {{
  if (confirm("Export the current report with all changes?")) {{
    let html = document.documentElement.outerHTML;
    let blob = new Blob([html], {{type: "text/html"}});
    let a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "Bosch_Report_" + new Date().toISOString().slice(0,10) + ".html";
    a.click();
    alert("Report exported successfully!");
  }}
}}

// Add keyboard shortcut for password entry
document.getElementById("pwdInput")?.addEventListener("keypress", function(e) {{
  if (e.key === "Enter") {{
    checkPassword();
  }}
}});
</script>
</body>
</html>
"""
    return html_content

# Enhanced Tkinter GUI with retro DOS theme
def run_gui():
    root = tk.Tk()
    root.title("BOSCH SECURITY SYSTEMS - REPORT GENERATOR v2.0")
    root.geometry("700x450")
    root.resizable(False, False)
    
    # Dark theme colors
    bg_color = "#0c0c0c"
    fg_color = "#00ff00"
    input_bg = "#1a1a1a"
    button_bg = "#0f4c0f"
    button_hover = "#1a6b1a"
    error_color = "#ff3333"
    
    # Configure window
    root.configure(bg=bg_color)
    
    # Main frame with dark background
    main_frame = tk.Frame(root, bg=bg_color, padx=30, pady=20)
    main_frame.pack(fill="both", expand=True)
    
    # ASCII Art Header  
    header_text = """╔══════════════════════════════════════════════════════════════════╗
║          BOSCH SECURITY SYSTEMS - ACCESS CONTROL                 ║
║                   REPORT GENERATOR v2.0                          ║
╚══════════════════════════════════════════════════════════════════╝"""
    
    header_label = tk.Label(main_frame, text=header_text, font=('Courier', 10), 
                           bg=bg_color, fg=fg_color, justify="left")
    header_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
    
    # File selection
    tk.Label(main_frame, text="[1] INPUT FILE:", font=('Courier', 11, 'bold'), 
            bg=bg_color, fg=fg_color).grid(row=1, column=0, sticky="w", pady=8)
    
    file_entry = tk.Entry(main_frame, width=45, font=('Courier', 10), 
                         bg=input_bg, fg=fg_color, insertbackground=fg_color,
                         highlightbackground="#2a2a2a", highlightcolor=fg_color)
    file_entry.grid(row=1, column=1, pady=8, padx=(10, 10))
    
    def browse_file():
        filename = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if filename:
            file_entry.delete(0, tk.END)
            file_entry.insert(0, filename)
    
    browse_btn1 = tk.Button(main_frame, text="[ BROWSE ]", command=browse_file,
                           font=('Courier', 10, 'bold'), bg=button_bg, fg=fg_color,
                           activebackground=button_hover, activeforeground=fg_color,
                           bd=1, relief="solid", padx=10)
    browse_btn1.grid(row=1, column=2, pady=8)
    
    # Password field
    tk.Label(main_frame, text="[2] PASSWORD:", font=('Courier', 11, 'bold'), 
            bg=bg_color, fg=fg_color).grid(row=2, column=0, sticky="w", pady=8)
    
    pwd_entry = tk.Entry(main_frame, show="*", width=45, font=('Courier', 10), 
                        bg=input_bg, fg=fg_color, insertbackground=fg_color,
                        highlightbackground="#2a2a2a", highlightcolor=fg_color)
    pwd_entry.grid(row=2, column=1, pady=8, padx=(10, 10))
    
    # Logo selection
    tk.Label(main_frame, text="[3] LOGO FILE:", font=('Courier', 11, 'bold'), 
            bg=bg_color, fg=fg_color).grid(row=3, column=0, sticky="w", pady=8)
    
    logo_entry = tk.Entry(main_frame, width=45, font=('Courier', 10), 
                         bg=input_bg, fg=fg_color, insertbackground=fg_color,
                         highlightbackground="#2a2a2a", highlightcolor=fg_color)
    logo_entry.grid(row=3, column=1, pady=8, padx=(10, 10))
    
    def browse_logo():
        filename = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg")])
        if filename:
            logo_entry.delete(0, tk.END)
            logo_entry.insert(0, filename)
    
    browse_btn2 = tk.Button(main_frame, text="[ BROWSE ]", command=browse_logo,
                           font=('Courier', 10, 'bold'), bg=button_bg, fg=fg_color,
                           activebackground=button_hover, activeforeground=fg_color,
                           bd=1, relief="solid", padx=10)
    browse_btn2.grid(row=3, column=2, pady=8)
    
    # Separator line
    separator = tk.Label(main_frame, text="─" * 70, font=('Courier', 10), 
                        bg=bg_color, fg="#333333")
    separator.grid(row=4, column=0, columnspan=3, pady=15)
    
    # Status display
    status_frame = tk.Frame(main_frame, bg=bg_color)
    status_frame.grid(row=5, column=0, columnspan=3, pady=10)
    
    status_prefix = tk.Label(status_frame, text="STATUS:", font=('Courier', 11, 'bold'), 
                            bg=bg_color, fg=fg_color)
    status_prefix.pack(side="left")
    
    status_label = tk.Label(status_frame, text="READY", font=('Courier', 11), 
                           bg=bg_color, fg=fg_color)
    status_label.pack(side="left", padx=(10, 0))
    
    # Generate button
    def generate_report():
        if not file_entry.get():
            status_label.config(text="ERROR: NO INPUT FILE SELECTED", fg=error_color)
            return
        
        try:
            status_label.config(text="PROCESSING...", fg=fg_color)
            root.update()
            
            data = parse_bosch_txt(file_entry.get())
            
            if not data:
                status_label.config(text="WARNING: NO DATA FOUND", fg=error_color)
                return
            
            logo_data = None
            if logo_entry.get():
                logo_data = process_logo(logo_entry.get())
                if logo_data is None:
                    # User cancelled or error occurred (already handled in process_logo)
                    return
            
            html = generate_html(data, pwd_entry.get(), logo_data)
            
            default_name = f"Bosch_Report_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.html"
            save_path = filedialog.asksaveasfilename(
                defaultextension=".html",
                initialfile=default_name,
                filetypes=[("HTML files", "*.html")]
            )
            
            if save_path:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(html)
                status_label.config(text=f"SUCCESS: REPORT SAVED [{len(data)} USERS]", fg=fg_color)
            else:
                status_label.config(text="OPERATION CANCELLED", fg=fg_color)
                
        except Exception as e:
            status_label.config(text=f"ERROR: {str(e)[:40]}", fg=error_color)
    
    # Button frame for centering
    button_frame = tk.Frame(main_frame, bg=bg_color)
    button_frame.grid(row=6, column=0, columnspan=3, pady=20)
    
    generate_btn = tk.Button(button_frame, text="[ GENERATE REPORT ]", command=generate_report,
                            font=('Courier', 12, 'bold'), bg=button_bg, fg=fg_color,
                            activebackground=button_hover, activeforeground=fg_color,
                            bd=2, relief="solid", padx=20, pady=8)
    generate_btn.pack()
    
    # Footer
    footer_text = "─" * 70 + "\nBOSCH SECURITY SYSTEMS (C) 2024 - AUTHORIZED USE ONLY"
    footer_label = tk.Label(main_frame, text=footer_text, font=('Courier', 9), 
                           bg=bg_color, fg="#666666", justify="center")
    footer_label.grid(row=7, column=0, columnspan=3, pady=(20, 0))
    
    # Center the window
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')
    
    # Bind hover effects
    def on_enter(e):
        e.widget.config(bg=button_hover)
    
    def on_leave(e):
        e.widget.config(bg=button_bg)
    
    for btn in [browse_btn1, browse_btn2, generate_btn]:
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
    
    root.mainloop()

if __name__ == "__main__":
    run_gui()