import os
import re

file_path = r"d:\RFID\frontend\js\components\navbar.js"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

logout_html = """
    <div class="p-4 mt-auto border-t border-gray-700">
        <button onclick="window.handleLogout()" class="w-full flex items-center gap-3 px-4 py-3 text-red-400 hover:text-white hover:bg-red-600 rounded-lg transition-colors">
            <i class="fas fa-sign-out-alt"></i>
            <span class="font-medium">Logout</span>
        </button>
    </div>
    </aside>
"""

content = content.replace("</aside>", logout_html)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

js_path = r"d:\RFID\frontend\js\app.js"
with open(js_path, "r", encoding="utf-8") as f:
    js_content = f.read()

logout_js = """
window.handleLogout = async () => {
    if(confirm("Are you sure you want to log out?")) {
        await fetch('/api/auth/logout', {method: 'POST'});
        window.location.href = '/login.html';
    }
};
"""
if "handleLogout" not in js_content:
    with open(js_path, "a", encoding="utf-8") as f:
        f.write("\n" + logout_js)

