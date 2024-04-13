import os

# Directory where the HTML files are stored
directory = "./data/HTML/"
# Root directory for the index.html
root_directory = "./"

# List only HTML files in the specified directory
files = sorted([f for f in os.listdir(directory) if f.endswith('.html')])

# Generate HTML for the index file
index_html = """
<html>
<head>
    <title>NASDAQ 100 Futures Charts Index</title>
    <style>
        body { font-family: Arial, sans-serif; display: flex; height: 100vh; margin: 0; }
        #navbar { overflow-y: auto; width: 300px; height: 100%; border-right: 1px solid #ccc; }
        #content { flex-grow: 1; }
        iframe { width: 100%; height: 100%; border: none; }
    </style>
</head>
<body>
    <div id="navbar">
        <ul style="list-style-type: none; padding: 20px;">
"""

# Creating links that point to the HTML files in the data/HTML directory
for file in files:
    display_name = file.replace('_', ' ').replace('.html', '')
    index_html += f'<li><a href="data/HTML/{file}" target="contentFrame">{display_name}</a></li>\n'

index_html += """
        </ul>
    </div>
    <div id="content">
        <iframe name="contentFrame"></iframe>
    </div>
</body>
</html>
"""

# Save the index.html in the root directory
index_file_path = os.path.join(root_directory, "index.html")
with open(index_file_path, "w") as f:
    f.write(index_html)
