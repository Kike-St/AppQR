from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import qrcode
import sqlite3
import io
from pyzbar.pyzbar import decode
from PIL import Image
import cv2
from twilio.rest import Client


account_sid = 'AC25499fcf4ea7d02c0ad772a296bf54c6'
auth_token = '2cb6986802ddc8093adae0fb82fd82c7'
twilio_phone_number = 'whatsapp:+14155238886'
client = Client(account_sid, auth_token)




app = Flask(__name__)
app.secret_key = 'your_secret_key'  

# Función para verificar la extensión de archivo permitida
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg'}

# Configuración de la base de datos (crea una base de datos SQLite llamada 'usuarios.db')
db = sqlite3.connect('usuarios.db', check_same_thread=False)
cursor = db.cursor()

# Crear una tabla 'users' si no existe
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        password TEXT NOT NULL,
        qr_img BLOB
    )
''')
db.commit()

# Rutas y lógica de la aplicación

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        phone_number = request.form['phone_number']

        # Verifica si el usuario ya existe en la base de datos
        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash("El usuario ya existe. Intente con otro nombre de usuario.", "error")
        else:
            # Genera un código QR único para el usuario
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(username)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")

            # Convierte la imagen a bytes
            img_buffer = io.BytesIO()
            qr_img.save(img_buffer)
            qr_img_bytes = img_buffer.getvalue()
            img_buffer.close()

            # Guarda los datos del usuario y el código QR en la base de datos
            cursor.execute("INSERT INTO users (username, password, qr_img, phone_number) VALUES (?, ?, ?, ?)", (username, password, qr_img_bytes, phone_number))
            db.commit()

            flash("Registro exitoso. Puede iniciar sesión con su nombre de usuario.", "success")
            return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not password:
            # Verificar si se proporcionó una imagen de código QR
            if 'qr_image' in request.files:
                qr_image = request.files['qr_image']

                if qr_image and allowed_file(qr_image.filename):
                    qr_image.save('temp_qr.png')
                    decoded_qr = decode(Image.open('temp_qr.png'))

                    if decoded_qr:
                        qr_content = decoded_qr[0].data.decode('utf-8')
                        cursor.execute("SELECT * FROM users WHERE username=? AND qr_img IS NOT NULL", (qr_content,))
                        user = cursor.fetchone()

                        if user:
                            session['user'] = user[1]
                            flash("Inicio de sesión exitoso.", "success")
                            phone_number = user[3]
                            # Luego, puedes usar este número para enviar un mensaje de notificación
                            send_notification(phone_number, "Has iniciado sesión correctamente en nuestra aplicación.")
                            return redirect(url_for('dashboard'))
                            
                        else:
                            flash("No se encontró un usuario correspondiente al código QR.", "error")
                    else:
                        flash("No se pudo decodificar el código QR.", "error")
                else:
                    flash("El archivo de imagen proporcionado no es válido.", "error")
            else:
                flash("No se proporcionó una imagen de código QR.", "error")
                return redirect(url_for('login'))
        else:
            cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
            user = cursor.fetchone()

            if user:
                session['user'] = user[1]
                flash("Inicio de sesión exitoso.", "success")
                return redirect(url_for('dashboard'))
            else:
                flash("Credenciales incorrectas. Intente nuevamente.", "error")

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    qr_content = request.args.get('qr')

    if 'user' in session:
        username = session['user']
        return render_template('dashboard.html', username=username)
    
    if qr_content:
        cursor.execute("SELECT * FROM users WHERE username=? AND qr_img IS NOT NULL", (qr_content,))
        user = cursor.fetchone()

        if user:
            session['user'] = user[1]  # Iniciar sesión automáticamente

             # Envía una notificación de WhatsApp al usuario
            phone_number = user[3]  # Recoge el número de teléfono del usuario
            send_notification(phone_number, "Has iniciado sesión correctamente en nuestra aplicación.")

            flash("Inicio de sesión exitoso.", "success")
            return render_template('dashboard.html', username=user[1])

    flash("Debe iniciar sesión para acceder al panel de control.", "error")
    return redirect(url_for('login'))


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

@app.route('/view_qr')
def view_qr():
    if 'user' in session:
        username = session['user']
        cursor.execute("SELECT qr_img FROM users WHERE username=?", (username,))
        qr_img = cursor.fetchone()
        
        if qr_img:
            qr_img = bytes(qr_img[0])
            return send_file(io.BytesIO(qr_img), mimetype='image/png')
        else:
            flash("No se encontró un código QR para este usuario.", "error")
            return redirect(url_for('dashboard'))
    else:
        flash("Debe iniciar sesión para ver su código QR.", "error")
        return redirect(url_for('login'))

@app.route('/download_qr')
def download_qr():
    if 'user' in session:
        username = session['user']
        cursor.execute("SELECT qr_img FROM users WHERE username=?", (username,))
        qr_img = cursor.fetchone()

        if qr_img:
            qr_img = bytes(qr_img[0])
            response = send_file(io.BytesIO(qr_img), mimetype='image/png', as_attachment=True, download_name='codigo_qr.png')
            response.headers["Content-Disposition"] = f"attachment; filename=codigo_qr.png"
            return response
        else:
            flash("No se encontró un código QR para este usuario.", "error")
            return redirect(url_for('dashboard'))
    else:
        flash("Debe iniciar sesión para descargar su código QR.", "error")
        return redirect(url_for('login'))

@app.route('/camera_login', methods=['GET', 'POST'])
def camera_login():
    if request.method == 'POST':
        if 'user' in session:
            session.pop('user', None)  # Limpiar la sesión actual antes de iniciar con la cámara

        cap = cv2.VideoCapture(0)

        while True:
            ret, frame = cap.read()

            if not ret:
                continue

            # Decodificar el código QR desde la imagen
            decoded_qr = decode(frame)

            if decoded_qr:
                qr_content = decoded_qr[0].data.decode('utf-8')
                cursor.execute("SELECT * FROM users WHERE username=? AND qr_img IS NOT NULL", (qr_content,))
                user = cursor.fetchone()

                if user:
                    session['user'] = user[1]  # Iniciar sesión automáticamente
                    cap.release()
                    cv2.destroyAllWindows()
                    flash("Inicio de sesión exitoso.", "success")
                    return redirect(url_for('dashboard'))

            cv2.imshow('Cámara', frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

    return render_template('camera_login.html')



# Función para enviar un mensaje de WhatsApp
def send_notification(phone_number, message):
    client = Client(account_sid, auth_token)
    try:
        message = client.messages.create(
        from_='whatsapp:+14155238886',
        body='Inicio de sesión correcto en CU',
        to='whatsapp:+5215515972247'
        )
        print(f"Mensaje enviado con SID: {message.sid}")
    except Exception as e:
        print(f"Error al enviar el mensaje: {e}")



if __name__ == '__main__':
    app.run(debug=True)