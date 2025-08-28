from flask import Flask, request, render_template, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/log-ip', methods=['POST'])
def log_ip():
    data = request.get_json()
    public_ip = data.get("public_ip")
    server_ip = request.remote_addr

    print(f"[CLIENT PUBLIC IP] {public_ip}")
    print(f"[CLIENT SERVER IP] {server_ip}")

    return jsonify({"status": "success", "server_ip": server_ip})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
