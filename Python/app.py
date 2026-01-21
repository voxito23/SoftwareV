from flask import Flask, render_template, request, send_file, flash, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import io
import os
import re

# -------------------- CONFIG --------------------
base_dir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = "lbv_style_secret_v1"

db_path = os.path.join(base_dir, "database.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


# -------------------- MODELOS --------------------
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)


class Tarjeta(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    numero = db.Column(db.String(16), unique=True, nullable=False)
    nombre_titular = db.Column(db.String(100), nullable=False)
    rfc = db.Column(db.String(13), nullable=False)              # 13 chars
    fecha_expiracion = db.Column(db.String(5), nullable=False)  # MM/YY
    cvv = db.Column(db.String(3), nullable=False)

    intentos = db.Column(db.Integer, default=0)
    fondos = db.Column(db.Float, default=0.0)
    verificada = db.Column(db.Boolean, default=True)

    # Dirección de facturación asociada a la tarjeta (opcional)
    bill_calle = db.Column(db.String(120), nullable=True)
    bill_num_ext = db.Column(db.String(20), nullable=True)
    bill_num_int = db.Column(db.String(20), nullable=True)
    bill_colonia = db.Column(db.String(120), nullable=True)
    bill_municipio = db.Column(db.String(120), nullable=True)
    bill_estado = db.Column(db.String(120), nullable=True)
    bill_cp = db.Column(db.String(5), nullable=True)
    bill_pais = db.Column(db.String(60), nullable=True)
    bill_telefono = db.Column(db.String(10), nullable=True)


class Orden(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)

    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    total = db.Column(db.Float, nullable=False)

    # Datos del pago usado (solo referencia)
    tarjeta_last4 = db.Column(db.String(4), nullable=False)
    tarjeta_id = db.Column(db.Integer, db.ForeignKey("tarjeta.id"), nullable=True)

    # Datos de facturación capturados al pagar (los que deben salir en factura)
    fact_nombre = db.Column(db.String(100), nullable=False)
    fact_rfc = db.Column(db.String(13), nullable=False)
    fact_calle = db.Column(db.String(120), nullable=False)
    fact_num_ext = db.Column(db.String(20), nullable=False)
    fact_num_int = db.Column(db.String(20), nullable=True)
    fact_colonia = db.Column(db.String(120), nullable=False)
    fact_municipio = db.Column(db.String(120), nullable=False)
    fact_estado = db.Column(db.String(120), nullable=False)
    fact_cp = db.Column(db.String(5), nullable=False)
    fact_pais = db.Column(db.String(60), nullable=False)
    fact_telefono = db.Column(db.String(10), nullable=False)

    user = db.relationship("Usuario", backref=db.backref("ordenes", lazy=True))
    tarjeta = db.relationship("Tarjeta", backref=db.backref("ordenes", lazy=True))


class OrdenItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    orden_id = db.Column(db.Integer, db.ForeignKey("orden.id"), nullable=False)

    producto_id = db.Column(db.Integer, db.ForeignKey("producto.id"), nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    imagen = db.Column(db.String(200), nullable=True)

    qty = db.Column(db.Integer, nullable=False)
    precio_unit = db.Column(db.Float, nullable=False)
    specs = db.Column(db.Text, nullable=True)

    orden = db.relationship("Orden", backref=db.backref("items", lazy=True))
    producto = db.relationship("Producto")


    # Dirección de facturación asociada a la tarjeta (opcional)
    bill_calle = db.Column(db.String(120), nullable=True)
    bill_num_ext = db.Column(db.String(20), nullable=True)
    bill_num_int = db.Column(db.String(20), nullable=True)
    bill_colonia = db.Column(db.String(120), nullable=True)
    bill_municipio = db.Column(db.String(120), nullable=True)
    bill_estado = db.Column(db.String(120), nullable=True)
    bill_cp = db.Column(db.String(5), nullable=True)            # 5
    bill_pais = db.Column(db.String(60), nullable=True)
    bill_telefono = db.Column(db.String(10), nullable=True)      # 10


class UserTarjeta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    tarjeta_id = db.Column(db.Integer, db.ForeignKey("tarjeta.id"), nullable=False)

    user = db.relationship("Usuario", backref=db.backref("tarjetas_guardadas", lazy=True))
    tarjeta = db.relationship("Tarjeta", backref=db.backref("usuarios_guardada", lazy=True))


class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    nombre = db.Column(db.String(140), nullable=False)
    categoria = db.Column(db.String(30), nullable=False)  # Steam, AliExpress, Xbox, Amazon, Accesorios
    tipo = db.Column(db.String(20), nullable=False)       # gift, consola, hardware, accesorio

    descripcion = db.Column(db.Text, nullable=False)
    specs = db.Column(db.Text, nullable=False)

    precio_base = db.Column(db.Float, nullable=False)
    comision_rate = db.Column(db.Float, nullable=False)    # 0.05 / 0.07
    precio_final = db.Column(db.Float, nullable=False)

    stock = db.Column(db.Integer, default=0)
    imagen = db.Column(db.String(200), nullable=False)     # giftX_Y.jpg / accX.jpg


# -------------------- HELPERS --------------------
def usuario_actual():
    u = session.get("user")
    if not u:
        return None
    return Usuario.query.filter_by(username=u).first()


def cart_get():
    return session.get("cart", {})


def cart_save(cart):
    session["cart"] = cart


def cart_total(cart):
    total = 0.0
    for _, item in cart.items():
        total += float(item["precio"]) * int(item["qty"])
    return total


def cart_items_list(cart):
    return list(cart.values())


def digits_only(s: str) -> str:
    return re.sub(r"\D+", "", s or "")


def buscar_imagen_segura(rel_path: str):
    if not rel_path:
        return None
    rel_path = rel_path.replace("\\", "/")
    ruta = os.path.join(app.static_folder, rel_path)
    if os.path.exists(ruta):
        return ruta
    return None


# -------------------- REGLAS DE PAGO --------------------
def validar_pago(datos, tarjeta: Tarjeta, total):
    """
    Regla 1: verificada + no expirada + cvv correcto + intentos no excedidos + fondos suficiente => autorizado
    Regla 2: no verificada => no autorizado
    Regla 3: expirada => no autorizado
    Regla 4: cvv incorrecto => no autorizado (+1 intento)
    Regla 5: intentos excedidos (>=3) => no autorizado (bloqueada)
    Regla 6: fondos insuficiente => no autorizado

    Extra (estilo Amazon):
    - nombre titular coincide
    - RFC coincide
    - exp coincide
    """
    if not tarjeta:
        return False, "Pago NO autorizado: Tarjeta no encontrada."

    if not tarjeta.verificada:
        return False, "Pago NO autorizado: Tarjeta no verificada."

    if tarjeta.intentos >= 3:
        return False, "Pago NO autorizado: Tarjeta bloqueada por intentos excedidos (3)."

    # Expiración (en BD)
    try:
        m, a = map(int, tarjeta.fecha_expiracion.split("/"))
        now = datetime.now()
        ac = int(str(now.year)[-2:])
        if (a < ac) or (a == ac and m < now.month):
            return False, "Pago NO autorizado: Tarjeta expirada."
    except:
        return False, "Pago NO autorizado: Fecha de expiración inválida en la tarjeta."

    # Exp ingresada debe coincidir
    if datos["fecha_expiracion"].strip() != tarjeta.fecha_expiracion.strip():
        tarjeta.intentos += 1
        db.session.commit()
        if tarjeta.intentos >= 3:
            return False, "Pago NO autorizado: Fecha no coincide. Tarjeta BLOQUEADA por 3 intentos."
        return False, "Pago NO autorizado: La fecha de expiración no coincide."

    # CVV
    if datos["cvv"] != tarjeta.cvv:
        tarjeta.intentos += 1
        db.session.commit()
        if tarjeta.intentos >= 3:
            return False, "Pago NO autorizado: CVV incorrecto. Tarjeta BLOQUEADA por 3 intentos."
        return False, "Pago NO autorizado: CVV incorrecto."

    # Titular
    if datos["nombre"].strip().upper() != tarjeta.nombre_titular.strip().upper():
        tarjeta.intentos += 1
        db.session.commit()
        if tarjeta.intentos >= 3:
            return False, "Pago NO autorizado: Titular no coincide. Tarjeta BLOQUEADA por 3 intentos."
        return False, "Pago NO autorizado: El titular no coincide con la tarjeta."

    # RFC
    if datos["rfc"].strip().upper() != tarjeta.rfc.strip().upper():
        tarjeta.intentos += 1
        db.session.commit()
        if tarjeta.intentos >= 3:
            return False, "Pago NO autorizado: RFC no coincide. Tarjeta BLOQUEADA por 3 intentos."
        return False, "Pago NO autorizado: El RFC no coincide con la tarjeta."

    # Fondos
    if tarjeta.fondos < total:
        return False, "Pago NO autorizado: Fondos insuficientes."

    # OK => descontar fondos y reset intentos
    tarjeta.fondos -= float(total)
    tarjeta.intentos = 0
    db.session.commit()
    return True, "Pago autorizado."


# -------------------- PDF --------------------
def _draw_logo(c, x, y, w=64, h=44):
    logo_path = buscar_imagen_segura("images/logo.jpg")
    if logo_path:
        try:
            c.drawImage(logo_path, x, y, w, h, mask="auto", preserveAspectRatio=True, anchor="c")
            return True
        except:
            return False
    return False
#--------------------------------------------------
def generar_pdf_factura(items, total, datos_fiscales, tarjeta: Tarjeta):
    """
    Factura (demo) en español:
    - Logo
    - Emisor
    - Receptor (datos capturados en pago: nombre/rfc + domicilio)
    - Tabla con mini-imagen por producto
    - IVA 16%
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    W, H = A4
    mx = 50

    AZUL = colors.HexColor("#148fb8")
    OSC = colors.HexColor("#0f172a")
    GR = colors.HexColor("#64748b")
    LINE = colors.HexColor("#e2e8f0")

    # Header
    c.setFillColor(colors.white)
    c.setStrokeColor(LINE)
    c.roundRect(mx, H - 115, W - 2 * mx, 75, 14, fill=1, stroke=1)

    _draw_logo(c, mx + 16, H - 104, 70, 50)

    c.setFillColor(OSC)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(mx + 95, H - 72, "LBV STORE")

    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 18)
    c.drawRightString(W - mx - 12, H - 72, "FACTURA")

    folio = f"F-EN-{datetime.now().strftime('%Y%m%d')}-{str(tarjeta.id).zfill(4)}"
    c.setFillColor(GR)
    c.setFont("Helvetica", 10)
    c.drawRightString(W - mx - 12, H - 92, f"Folio: {folio}")
    c.drawRightString(W - mx - 12, H - 106, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}")

    # Bloques emisor / receptor
    y = H - 155
    c.setFillColor(colors.white)
    c.setStrokeColor(LINE)
    left_w = (W - 2 * mx) / 2 - 8
    right_x = mx + (W - 2 * mx) / 2 + 8

    c.roundRect(mx, y - 78, left_w, 78, 12, fill=1, stroke=1)
    c.roundRect(right_x, y - 78, left_w, 78, 12, fill=1, stroke=1)

    # Emisor
    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(mx + 12, y - 22, "EMISOR")
    c.setFillColor(OSC)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(mx + 12, y - 40, "LBV STORE S.A. DE C.V.")
    c.setFillColor(GR)
    c.setFont("Helvetica", 9)
    c.drawString(mx + 12, y - 56, "RFC: LBS010101AA1")
    c.drawString(mx + 12, y - 68, "México (Demo Académica)")

    # Receptor (capturado en pago)
    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(right_x + 12, y - 22, "RECEPTOR (FACTURAR A)")
    c.setFillColor(OSC)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(right_x + 12, y - 40, datos_fiscales["nombre"][:40])  # CORRECCIÓN
    c.setFillColor(GR)
    c.setFont("Helvetica", 9)
    c.drawString(right_x + 12, y - 56, f"RFC: {datos_fiscales['rfc']}")  # CORRECCIÓN

    dom1 = f"{datos_fiscales['calle']} {datos_fiscales['num_ext']}"  # CORRECCIÓN
    if datos_fiscales['num_int']:
        dom1 += f" Int {datos_fiscales['num_int']}"
    c.drawString(right_x + 12, y - 68, dom1[:55])  # CORRECCIÓN

    # Método pago
    y2 = y - 95
    c.setFillColor(GR)
    c.setFont("Helvetica", 9)
    c.drawString(mx + 12, y2, "Método de pago:")
    c.setFillColor(OSC)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(mx + 95, y2, f"Tarjeta **** {tarjeta.numero[-4:]}")

    # Dirección expandida receptor
    c.setFillColor(GR)
    c.setFont("Helvetica", 9)
    c.drawString(right_x + 12, y2, f"{datos_fiscales['colonia']}, {datos_fiscales['municipio']}, {datos_fiscales['estado']} CP {datos_fiscales['cp']}")
    c.drawString(right_x + 12, y2 - 12, f"{datos_fiscales['pais']} • Tel: {datos_fiscales['telefono']}")

    # Tabla
    y = y2 - 35
    c.setStrokeColor(LINE)
    c.setLineWidth(1)
    c.line(mx, y, W - mx, y)
    y -= 18

    c.setFillColor(GR)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(mx, y, "DESCRIPCIÓN")
    c.drawRightString(W - mx - 140, y, "CANT.")
    c.drawRightString(W - mx - 70, y, "P. UNIT.")
    c.drawRightString(W - mx, y, "IMPORTE")

    y -= 10
    c.setStrokeColor(LINE)
    c.line(mx, y, W - mx, y)
    y -= 18

    for item in items:
        if y < 155:
            c.showPage()
            y = H - 80

        img_path = buscar_imagen_segura("images/" + item.get("imagen", ""))
        tx = mx
        if img_path:
            try:
                c.drawImage(img_path, mx, y - 6, 36, 28, preserveAspectRatio=True, mask="auto")
                tx = mx + 44
            except:
                tx = mx

        c.setFillColor(OSC)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(tx, y + 10, item["nombre"][:48])

        c.setFillColor(GR)
        c.setFont("Helvetica", 8)
        specs_short = (item.get("specs", "") or "").split("|")[0]
        c.drawString(tx, y - 2, specs_short[:60])

        qty = int(item["qty"])
        unit = float(item["precio"])
        line_total = qty * unit

        c.setFillColor(OSC)
        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(W - mx - 140, y + 8, str(qty))
        c.drawRightString(W - mx - 70, y + 8, f"${unit:,.2f}")
        c.drawRightString(W - mx, y + 8, f"${line_total:,.2f}")

        y -= 40
        c.setStrokeColor(LINE)
        c.setLineWidth(0.5)
        c.line(mx, y + 18, W - mx, y + 18)

    # Totales
    y -= 10
    subtotal = float(total) / 1.16
    iva = float(total) - subtotal

    c.setFillColor(GR)
    c.setFont("Helvetica", 10)
    c.drawRightString(W - mx - 90, y, "Subtotal:")
    c.setFillColor(OSC)
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(W - mx, y, f"${subtotal:,.2f}")

    y -= 16
    c.setFillColor(GR)
    c.setFont("Helvetica", 10)
    c.drawRightString(W - mx - 90, y, "IVA (16%):")
    c.setFillColor(OSC)
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(W - mx, y, f"${iva:,.2f}")

    y -= 18
    c.setStrokeColor(LINE)
    c.setLineWidth(1)
    c.line(W - mx - 200, y + 8, W - mx, y + 8)

    c.setFillColor(colors.HexColor("#0ea5e9"))
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(W - mx - 90, y - 6, "TOTAL:")
    c.drawRightString(W - mx, y - 6, f"${float(total):,.2f}")

    c.setFillColor(GR)
    c.setFont("Helvetica", 8)
    c.drawString(mx, 70, "")
    c.drawString(mx, 58, "Gracias por tu compra.")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

#........................................................

def generar_pdf_recibo(items, total, comprador_username: str):
    """
    Recibo más “bonito” con fondo oscuro + amarillo, mini imágenes.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    W, H = A4
    mx = 50

    OSC = colors.HexColor("#0b1220")
    AMAR = colors.HexColor("#f9f506")
    GR = colors.HexColor("#94a3b8")
    LINE = colors.HexColor("#1f2a44")

    # Header
    c.setFillColor(OSC)
    c.roundRect(mx, H - 125, W - 2 * mx, 90, 18, fill=1, stroke=0)

    _draw_logo(c, mx + 18, H - 105, 70, 50)

    c.setFillColor(AMAR)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(mx + 100, H - 78, "RECIBO DE COMPRA")

    c.setFillColor(colors.white)
    c.setFont("Helvetica", 10)
    c.drawString(mx + 100, H - 98, f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    c.drawRightString(W - mx - 16, H - 98, f"Usuario: {comprador_username}")

    # Lista
    y = H - 165
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#e2e8f0"))
    c.roundRect(mx, y - 520, W - 2 * mx, 520, 14, fill=1, stroke=1)

    y -= 30
    c.setFillColor(colors.HexColor("#0f172a"))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(mx + 16, y, "Productos")

    y -= 18
    c.setStrokeColor(colors.HexColor("#e2e8f0"))
    c.setLineWidth(1)
    c.line(mx + 16, y, W - mx - 16, y)
    y -= 26

    for item in items:
        img_path = buscar_imagen_segura("images/" + item.get("imagen", ""))
        tx = mx + 16

        if img_path:
            try:
                c.drawImage(img_path, mx + 16, y - 10, 44, 34, preserveAspectRatio=True, mask="auto")
                tx = mx + 70
            except:
                tx = mx + 16

        c.setFillColor(colors.HexColor("#0f172a"))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(tx, y + 12, item["nombre"][:48])

        c.setFillColor(colors.HexColor("#64748b"))
        c.setFont("Helvetica", 8)
        c.drawString(tx, y, (item.get("specs", "").split("|")[0])[:64])

        qty = int(item["qty"])
        unit = float(item["precio"])
        line_total = qty * unit

        c.setFillColor(colors.HexColor("#0f172a"))
        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(W - mx - 90, y + 10, f"x{qty}")
        c.drawRightString(W - mx - 16, y + 10, f"${line_total:,.2f}")

        y -= 48
        if y < 130:
            c.showPage()
            y = H - 80

    # Total
    c.setFillColor(OSC)
    c.roundRect(mx, 90, W - 2 * mx, 55, 14, fill=1, stroke=0)
    c.setFillColor(AMAR)
    c.setFont("Helvetica-Bold", 18)
    c.drawRightString(W - mx - 16, 114, f"TOTAL: ${float(total):,.2f}")

    c.setFillColor(GR)
    c.setFont("Helvetica", 8)
    c.drawString(mx, 60, "Recibo, GRACIAS POR SU COMPRA.")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


# INICIO DE BD
def inicializar_db():
    with app.app_context():
        db.create_all()

        if not Usuario.query.first():
            users = [
                {"username": "victor", "password": "victor2026"},
                {"username": "belen", "password": "belen2026"},
                {"username": "guadalupe", "password": "guada2026"},
                {"username": "admin", "password": "admin"},
            ]
            for u in users:
                db.session.add(Usuario(**u))
            db.session.commit()

        # 10 tarjetas preexistentes 
        if not Tarjeta.query.first():
            tarjetas = [
            ("4152313365897412", "JUAN PEREZ",   "PEJU800101H2A", "12/30", "123", 0, 500000.0, True,
             "Av Siempre Viva", "742", "", "Springfield", "Querétaro", "Querétaro", "76000", "México", "4421111111"),
            ("1111222233334444", "LUIS SANTANO",   "LUNO900101H2B", "12/28", "111", 0, 100000.0, False,
             "Calle 1", "100", "2", "Centro", "Huimilpan", "Querétaro", "76000", "México", "4422222222"),
            ("5555666677778888", "ANA RIVAS", "ANEX880202M3C", "01/20", "555", 0, 50000.0, True,
             "Calle 2", "200", "", "La Loma", "Querétaro", "Querétaro", "76116", "México", "4423333333"),
            ("9999888877776666", "PEDRO TORRES",  "PEPO770303H4D", "12/29", "999", 0, 10.0, True,
             "Calle 3", "300", "", "Centro", "Querétaro", "Querétaro", "76000", "México", "4424444444"),
            ("1234123412341234", "MARIA ANIEVAS",   "MABL990404M5E", "12/28", "000", 2, 50000.0, True,
             "Calle 4", "400", "", "Centro Sur", "Querétaro", "Querétaro", "76090", "México", "4425555555"),
            ("4000123456789010", "CARLOS RUIZ",  "RUC850505H60F", "05/28", "321", 0, 80000.0, True,
             "Calle 5", "500", "10", "Taponas", "Huimilpan", "Querétaro", "76000", "México", "4426666666"),
            ("5100000000000000", "SOFIA LUNA",   "SOLU920606M7G", "08/29", "777", 0, 150000.0, True,
             "Calle 6", "600", "", "Centro", "Querétaro", "Querétaro", "76000", "México", "4427777777"),
            ("4200000000000000", "JORGE JUSTO",  "JOJU810707H8H", "09/30", "888", 0, 40000.0, True,
             "Calle 7", "700", "", "La Loma", "Querétaro", "Querétaro", "76116", "México", "4428888888"),
            ("3400000000000000", "DIANA NOVER",  "DINO950808M9I", "10/28", "444", 0, 60000.0, False,
             "Calle 8", "800", "", "Centro Sur", "Querétaro", "Querétaro", "76090", "México", "4429999999"),
            ("6011000000000000", "OSVALDO HERNANDEZ",   "TECV000101H0J", "11/30", "123", 0, 90000.0, True,
             "Calle 9", "900", "", "Centro", "Querétaro", "Querétaro", "76000", "México", "4421010101"),
            ]
            for t in tarjetas:
                db.session.add(Tarjeta(
                numero=t[0], nombre_titular=t[1], rfc=t[2], fecha_expiracion=t[3], cvv=t[4],
                intentos=t[5], fondos=t[6], verificada=t[7],
                bill_calle=t[8], bill_num_ext=t[9], bill_num_int=t[10], bill_colonia=t[11],
                bill_municipio=t[12], bill_estado=t[13], bill_cp=t[14], bill_pais=t[15], bill_telefono=t[16]
            ))
            db.session.commit()

        # Guardar algunas tarjetas por usuario 
        if not UserTarjeta.query.first():
            victor = Usuario.query.filter_by(username="victor").first()
            belen = Usuario.query.filter_by(username="belen").first()
            guada = Usuario.query.filter_by(username="guadalupe").first()

            t6 = Tarjeta.query.filter_by(numero="4000123456789010").first()
            t7 = Tarjeta.query.filter_by(numero="5100000000000000").first()
            t1 = Tarjeta.query.filter_by(numero="4152313365897412").first()

            if victor and t6:
                db.session.add(UserTarjeta(user_id=victor.id, tarjeta_id=t6.id))
            if belen and t7:
                db.session.add(UserTarjeta(user_id=belen.id, tarjeta_id=t7.id))
            if guada and t1:
                db.session.add(UserTarjeta(user_id=guada.id, tarjeta_id=t1.id))
            db.session.commit()

        # Productos 
        if not Producto.query.first():
            def add_prod(nombre, categoria, tipo, desc, specs, precio_base, rate, stock, imagen):
                precio_final = round(float(precio_base) * (1.0 + float(rate)), 2)
                db.session.add(Producto(
                    nombre=nombre,
                    categoria=categoria,
                    tipo=tipo,
                    descripcion=desc,
                    specs=specs,
                    precio_base=float(precio_base),
                    comision_rate=float(rate),
                    precio_final=float(precio_final),
                    stock=int(stock),
                    imagen=imagen
                ))

            # Steam 
            add_prod(
                "Steam Gift Card $100 MXN",
                "Steam",
                "gift",
                "Saldo digital para tu cuenta Steam. Entrega digital inmediata (demo).",
                "Región: MX|Plataforma: Steam|Entrega: Digital|Uso: Juegos, DLC, saldo|Comisión: 5%",
                100.0, 0.05, 50,
                "gift1_1.jpg"
            )
            add_prod(
                "Steam Gift Card $500 MXN",
                "Steam",
                "gift",
                "Código digital para recargar tu saldo en Steam. Entrega inmediata (demo).",
                "Región: MX|Plataforma: Steam|Entrega: Digital|Ideal: Regalo|Comisión: 5%",
                500.0, 0.05, 40,
                "gift1_2.jpg"
            )
            add_prod(
                "Steam Gift Card $2000 MXN",
                "Steam",
                "gift",
                "Recarga fuerte para compras grandes. Entrega digital inmediata (demo).",
                "Región: MX|Plataforma: Steam|Entrega: Digital|Ideal: AAA|Comisión: 5%",
                2000.0, 0.05, 25,
                "gift1_3.jpg"
            )
            add_prod(
                "Consola Portátil Steam Deck OLED 1TB",
                "Steam",
                "consola",
                "Consola portátil para PC gaming. Rendimiento sólido para SteamOS y juegos optimizados.",
                "Pantalla: 7.4\" HDR OLED 90Hz|Almacenamiento: 1TB NVMe|CPU/GPU: AMD APU (Zen/RDNA)|Batería: 3–12 hrs (según uso)|Conectividad: Wi-Fi + BT|Audio: Estéreo|Comisión: 7%",
                16999.0, 0.07, 6,
                "gift1_4.jpg"
            )

            # AliExpress 
            add_prod(
                "Cargador Essager 65W USB-C (GaN)",
                "AliExpress",
                "hardware",
                "Cargador rápido para laptop y teléfono. Estilo GaN compacto (demo).",
                "Potencia: 65W|Puertos: USB-C/USB-A|Tecnología: PD/QC|Uso: Laptop/Phone|Comisión: 7%",
                499.0, 0.07, 30,
                "gift2_1.jpg"
            )
            add_prod(
                "Cargador Essager 100W USB-C (GaN)",
                "AliExpress",
                "hardware",
                "Cargador de alta potencia para gaming laptop y dispositivos PD.",
                "Potencia: 100W|Puertos: USB-C|Tecnología: PD 3.0|Cable: depende del kit|Comisión: 7%",
                799.0, 0.07, 22,
                "gift2_2.jpg"
            )
            add_prod(
                "Memoria RAM DDR4 16GB (3200MHz)",
                "AliExpress",
                "hardware",
                "Upgrade clásico para mejorar multitarea y rendimiento.",
                "Capacidad: 16GB|Tipo: DDR4|Frecuencia: 3200MHz|Formato: depende (SODIMM/UDIMM)|Comisión: 7%",
                699.0, 0.07, 18,
                "gift2_3.jpg"
            )
            add_prod(
                "Mochila BANGE Antirrobo (Laptop)",
                "AliExpress",
                "hardware",
                "Mochila urbana resistente, con compartimento para laptop (demo).",
                "Capacidad: 20–25L|Protección: Antirrobo|Material: Resistente al agua|Laptop: hasta 15.6–17\"|Comisión: 7%",
                999.0, 0.07, 14,
                "gift2_4.jpg"
            )

            # Xbox 
            add_prod(
                "Xbox Gift Card $500 MXN",
                "Xbox",
                "gift",
                "Saldo digital para Microsoft Store / Xbox (demo).",
                "Región: MX|Plataforma: Xbox/Microsoft|Entrega: Digital|Comisión: 5%",
                500.0, 0.05, 35,
                "gift3_1.jpg"
            )
            add_prod(
                "Xbox Gift Card $2000 MXN",
                "Xbox",
                "gift",
                "Crédito para juegos, suscripciones y contenido digital (demo).",
                "Región: MX|Plataforma: Xbox/Microsoft|Entrega: Digital|Comisión: 5%",
                2000.0, 0.05, 18,
                "gift3_2.jpg"
            )
            add_prod(
                "Control Xbox Wireless (Bluetooth)",
                "Xbox",
                "hardware",
                "Control inalámbrico compatible con Xbox y PC.",
                "Conectividad: Bluetooth|Batería: AA/kit|Compatibilidad: Xbox/PC|Vibración: Sí|Comisión: 7%",
                1499.0, 0.07, 12,
                "gift3_3.jpg"
            )
            add_prod(
                "Consola Xbox One (Edición estándar)",
                "Xbox",
                "consola",
                "Consola para gaming y entretenimiento (demo).",
                "Resolución: hasta 1080p|Almacenamiento: según versión|Conectividad: Wi-Fi/Ethernet|Lector: según versión|Comisión: 7%",
                3999.0, 0.07, 5,
                "gift3_4.jpg"
            )

            # Amazon 
            add_prod(
                "Amazon Gift Card $1000 MXN",
                "Amazon",
                "gift",
                "Saldo digital para compras en Amazon (demo).",
                "Región: MX|Plataforma: Amazon|Entrega: Digital|Comisión: 5%",
                1000.0, 0.05, 28,
                "gift4_1.jpg"
            )
            add_prod(
                "Amazon Gift Card $1500 MXN",
                "Amazon",
                "gift",
                "Código digital para compras en Amazon (demo).",
                "Región: MX|Plataforma: Amazon|Entrega: Digital|Comisión: 5%",
                1500.0, 0.05, 22,
                "gift4_2.jpg"
            )
            add_prod(
                "Laptop ASUS ROG G16 (Gaming)",
                "Amazon",
                "hardware",
                "Laptop gamer con pantalla rápida y potencia para eSports/AAA (demo).",
                "Pantalla: 16\" alta frecuencia|CPU: Intel Core i7/i9 (según config)|GPU: RTX (según config)|RAM: 16–32GB|SSD: 1TB|Comisión: 7%",
                35999.0, 0.07, 4,
                "gift4_3.jpg"
            )
            add_prod(
                "Cartas Pokémon (Booster / Set)",
                "Amazon",
                "hardware",
                "Coleccionables Pokémon (demo).",
                "Tipo: Booster/Set|Ideal: Colección|Condición: Nueva|Notas: varía por set|Comisión: 7%",
                299.0, 0.07, 40,
                "gift4_4.jpg"
            )

            # Accesorios
            add_prod(
                "Audífonos Gamer (Micrófono)",
                "Accesorios",
                "accesorio",
                "Audífonos cómodos para jugar y llamadas.",
                "Mic: Sí|Conexión: 3.5mm/USB (según modelo)|Aislamiento: Medio|Comisión: 7%",
                699.0, 0.07, 20,
                "acc1.jpg"
            )
            add_prod(
                "Mouse Gamer RGB",
                "Accesorios",
                "accesorio",
                "Mouse preciso con RGB para gaming.",
                "DPI: ajustable|RGB: Sí|Conexión: USB|Comisión: 7%",
                399.0, 0.07, 35,
                "acc2.jpg"
            )
            add_prod(
                "Teclado Mecánico (Switches)",
                "Accesorios",
                "accesorio",
                "Teclado mecánico para escribir/jugar.",
                "Tipo: Mecánico|Anti-ghosting: Sí|Retroiluminación: Sí|Comisión: 7%",
                999.0, 0.07, 16,
                "acc3.jpg"
            )
            add_prod(
                "Base Enfriadora para Laptop",
                "Accesorios",
                "accesorio",
                "Ayuda a mantener temperaturas bajas en sesiones largas.",
                "Ventiladores: múltiples|Alimentación: USB|Ángulo: ajustable|Comisión: 7%",
                499.0, 0.07, 24,
                "acc4.jpg"
            )

            db.session.commit()


# AUTH
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = (request.form.get("username") or "").strip().lower()
        p = (request.form.get("password") or "").strip()

        user = Usuario.query.filter_by(username=u).first()
        if user and user.password == p:
            session["user"] = u
            if "cart" not in session:
                session["cart"] = {}
            return redirect(url_for("index"))
        flash("Datos incorrectos.", "error")

    return render_template("login.html")


@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = (request.form.get("password") or "").strip()

        if not username or not password:
            flash("Completa usuario y contraseña.", "error")
            return redirect(url_for("registro"))

        if Usuario.query.filter_by(username=username).first():
            flash("Ese usuario ya existe.", "error")
            return redirect(url_for("registro"))

        db.session.add(Usuario(username=username, password=password))
        db.session.commit()

        session["user"] = username
        session["cart"] = {}
        flash("Cuenta creada. Ya puedes comprar.", "success")
        return redirect(url_for("index"))

    return render_template("registro.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# -------------------- TIENDA --------------------
@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("login"))

    cat = request.args.get("cat", "Steam")
    categorias = ["Steam", "AliExpress", "Xbox", "Amazon"]

    if cat not in categorias:
        cat = "Steam"

    productos = Producto.query.filter_by(categoria=cat).all()
    accesorios = Producto.query.filter_by(categoria="Accesorios").all()

    return render_template(
        "index.html",
        cat=cat,
        categorias=categorias,
        productos=productos,
        accesorios=accesorios
    )


@app.route("/producto/<int:id>")
def detalle(id):
    if "user" not in session:
        return redirect(url_for("login"))

    p = Producto.query.get_or_404(id)
    accesorios = Producto.query.filter_by(categoria="Accesorios").all()

    reseñas = [
        dict(nombre="Mario R.", avatar="avatars/u1.jpg", rating=5, texto="Llegó rápido y todo bien. Buen precio."),
        dict(nombre="Karen V.", avatar="avatars/u2.jpg", rating=5, texto="Buena compra, y la comisión está clara."),
        dict(nombre="Luis A.", avatar="avatars/u3.jpg", rating=4, texto="Todo ok, solo cuida el stock."),
        dict(nombre="Gaby C.", avatar="avatars/u4.jpg", rating=5, texto="Interfaz tipo LBV, me gustó."),
    ]

    return render_template("detalle.html", p=p, accesorios=accesorios, reseñas=reseñas)


# -------------------- CARRITO --------------------
@app.route("/add/<int:id>", methods=["POST"])
def add_cart(id):
    if "user" not in session:
        return redirect(url_for("login"))

    p = Producto.query.get_or_404(id)
    if p.stock <= 0:
        flash("Sin stock.", "error")
        return redirect(request.referrer or url_for("index"))

    try:
        qty = int(request.form.get("qty", "1"))
        qty = max(1, qty)
    except:
        qty = 1

    cart = cart_get()
    key = str(id)
    current = int(cart.get(key, {}).get("qty", 0))
    if current + qty > int(p.stock):
        flash("No hay suficiente stock para esa cantidad.", "error")
        return redirect(request.referrer or url_for("index"))

    if key not in cart:
        cart[key] = {
            "id": p.id,
            "nombre": p.nombre,
            "precio": float(p.precio_final),
            "imagen": p.imagen,
            "specs": p.specs,
            "qty": qty,
            "stock": int(p.stock),
            "categoria": p.categoria,
            "tipo": p.tipo
        }
    else:
        cart[key]["qty"] = current + qty
        cart[key]["stock"] = int(p.stock)

    cart_save(cart)
    flash("Agregado al carrito.", "success")
    return redirect(request.referrer or url_for("index"))


@app.route("/cart/plus/<int:id>")
def cart_plus(id):
    if "user" not in session:
        return redirect(url_for("login"))

    p = Producto.query.get_or_404(id)
    cart = cart_get()
    key = str(id)

    if key in cart:
        if int(cart[key]["qty"]) + 1 > int(p.stock):
            flash("No hay más stock.", "error")
            return redirect(url_for("carrito"))
        cart[key]["qty"] = int(cart[key]["qty"]) + 1
        cart[key]["stock"] = int(p.stock)
        cart_save(cart)

    return redirect(url_for("carrito"))


@app.route("/cart/minus/<int:id>")
def cart_minus(id):
    if "user" not in session:
        return redirect(url_for("login"))

    cart = cart_get()
    key = str(id)
    if key in cart:
        q = int(cart[key]["qty"]) - 1
        if q <= 0:
            cart.pop(key, None)
        else:
            cart[key]["qty"] = q
        cart_save(cart)

    return redirect(url_for("carrito"))


@app.route("/cart/remove/<int:id>")
def cart_remove(id):
    if "user" not in session:
        return redirect(url_for("login"))

    cart = cart_get()
    cart.pop(str(id), None)
    cart_save(cart)
    return redirect(url_for("carrito"))


@app.route("/carrito")
def carrito():
    if "user" not in session:
        return redirect(url_for("login"))

    cart = cart_get()

    # refrescar stock real
    for k in list(cart.keys()):
        prod = Producto.query.get(int(k))
        if not prod:
            cart.pop(k, None)
            continue
        cart[k]["stock"] = int(prod.stock)
        if int(cart[k]["qty"]) > int(prod.stock):
            cart[k]["qty"] = int(prod.stock)

    cart_save(cart)
    total = cart_total(cart)
    return render_template("carrito.html", cart=cart_items_list(cart), total=total)


@app.route("/vaciar")
def vaciar():
    session["cart"] = {}
    return redirect(url_for("carrito"))


# -------------------- PAGO (FACTURA SE CAPTURA AQUI) --------------------
@app.route("/pagar", methods=["GET", "POST"])
def pagar():
    if "user" not in session:
        return redirect(url_for("login"))

    user = usuario_actual()
    if not user:
        return redirect(url_for("logout"))

    cart = cart_get()
    if not cart:
        return redirect(url_for("index"))

    # Validar stock antes de pagar
    for k in cart.keys():
        prod = Producto.query.get(int(k))
        if not prod or int(prod.stock) < int(cart[k]["qty"]):
            flash("Uno o más productos ya no tienen stock suficiente. Ajusta tu carrito.", "error")
            return redirect(url_for("carrito"))

    total = cart_total(cart)
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")

    # Tarjetas guardadas del usuario
    guardadas = []
    for rel in user.tarjetas_guardadas:
        t = Tarjeta.query.get(rel.tarjeta_id)
        if t:
            guardadas.append(t)

    if request.method == "POST":
        # Datos requeridos del pago (actividad)
        nombre = (request.form.get("nombre") or "").strip()
        rfc = (request.form.get("rfc") or "").strip().upper()
        numero_tarjeta = digits_only(request.form.get("numero_tarjeta") or "")
        fecha_exp = (request.form.get("fecha_expiracion") or "").strip()
        cvv = digits_only(request.form.get("cvv") or "")

        # Validaciones simples
        if len(rfc) != 13:
            flash("RFC debe tener EXACTAMENTE 13 caracteres.", "error")
            return render_template("pago.html", cart=cart_items_list(cart), total=total, fecha_hoy=fecha_hoy, guardadas=guardadas)

        if len(numero_tarjeta) != 16:
            flash("La tarjeta debe tener 16 dígitos.", "error")
            return render_template("pago.html", cart=cart_items_list(cart), total=total, fecha_hoy=fecha_hoy, guardadas=guardadas)

        if len(cvv) != 3:
            flash("CVV debe tener 3 dígitos.", "error")
            return render_template("pago.html", cart=cart_items_list(cart), total=total, fecha_hoy=fecha_hoy, guardadas=guardadas)

        t = Tarjeta.query.filter_by(numero=numero_tarjeta).first()
        if not t:
            flash("Pago NO autorizado: Tarjeta no encontrada.", "error")
            return render_template("pago.html", cart=cart_items_list(cart), total=total, fecha_hoy=fecha_hoy, guardadas=guardadas)

        # Domicilio fiscal: opción del cliente (usar el de tarjeta o capturar otro)
        usar_domicilio_tarjeta = request.form.get("usar_domicilio_tarjeta") == "1"

        if usar_domicilio_tarjeta:
            datos_fiscales = {
                "nombre": nombre,
                "rfc": rfc,
                "calle": (t.bill_calle or "").strip(),
                "num_ext": (t.bill_num_ext or "").strip(),
                "num_int": (t.bill_num_int or "").strip(),
                "colonia": (t.bill_colonia or "").strip(),
                "municipio": (t.bill_municipio or "").strip(),
                "estado": (t.bill_estado or "").strip(),
                "cp": digits_only(t.bill_cp or ""),
                "pais": (t.bill_pais or "México").strip(),
                "telefono": digits_only(t.bill_telefono or "")
            }
            # Si la tarjeta no tiene domicilio guardado completo, obligar a capturar
            if not all([datos_fiscales["calle"], datos_fiscales["num_ext"], datos_fiscales["colonia"], datos_fiscales["municipio"], datos_fiscales["estado"]]) or len(datos_fiscales["cp"]) != 5 or len(datos_fiscales["telefono"]) != 10:
                flash("Esa tarjeta no tiene domicilio de facturación completo. Captúralo manualmente.", "error")
                return render_template("pago.html", cart=cart_items_list(cart), total=total, fecha_hoy=fecha_hoy, guardadas=guardadas)
        else:
            calle = (request.form.get("calle") or "").strip()
            num_ext = (request.form.get("num_ext") or "").strip()
            num_int = (request.form.get("num_int") or "").strip()
            colonia = (request.form.get("colonia") or "").strip()
            municipio = (request.form.get("municipio") or "").strip()
            estado = (request.form.get("estado") or "").strip()
            cp = digits_only(request.form.get("cp") or "")
            pais = (request.form.get("pais") or "México").strip()
            telefono = digits_only(request.form.get("telefono") or "")

            if len(cp) != 5:
                flash("CP debe tener 5 dígitos.", "error")
                return render_template("pago.html", cart=cart_items_list(cart), total=total, fecha_hoy=fecha_hoy, guardadas=guardadas)

            if len(telefono) != 10:
                flash("Teléfono debe tener 10 dígitos.", "error")
                return render_template("pago.html", cart=cart_items_list(cart), total=total, fecha_hoy=fecha_hoy, guardadas=guardadas)

            if not (calle and num_ext and colonia and municipio and estado):
                flash("Completa el domicilio de facturación.", "error")
                return render_template("pago.html", cart=cart_items_list(cart), total=total, fecha_hoy=fecha_hoy, guardadas=guardadas)

            datos_fiscales = {
                "nombre": nombre,
                "rfc": rfc,
                "calle": calle,
                "num_ext": num_ext,
                "num_int": num_int,
                "colonia": colonia,
                "municipio": municipio,
                "estado": estado,
                "cp": cp,
                "pais": pais,
                "telefono": telefono
            }

        datos_pago = {
            "nombre": nombre,
            "rfc": rfc,
            "numero_tarjeta": numero_tarjeta,
            "fecha_expiracion": fecha_exp,
            "cvv": cvv
        }

        ok, msg = validar_pago(datos_pago, t, total)
        if not ok:
            flash(msg, "error")
            return render_template("pago.html", cart=cart_items_list(cart), total=total, fecha_hoy=fecha_hoy, guardadas=guardadas)

        # Descontar STOCK
        for k, item in cart.items():
            prod = Producto.query.get(int(k))
            if not prod:
                flash("Error: producto inválido.", "error")
                return redirect(url_for("carrito"))
            if int(prod.stock) < int(item["qty"]):
                flash("Se acabó el stock durante el pago. Ajusta tu carrito.", "error")
                return redirect(url_for("carrito"))
            prod.stock = int(prod.stock) - int(item["qty"])
        db.session.commit()

        # Guardar tarjeta (opcional)
        if request.form.get("guardar_tarjeta") == "1":
            existe = UserTarjeta.query.filter_by(user_id=user.id, tarjeta_id=t.id).first()
            if not existe:
                db.session.add(UserTarjeta(user_id=user.id, tarjeta_id=t.id))
                db.session.commit()
        # ---------------- GUARDAR ORDEN EN BD (HISTORIAL) ----------------
        # Datos de facturación: si el usuario marcó usar domicilio de tarjeta y existe completo,
        # úsalo; si no, usa los campos manuales del form.
        usar_dom = request.form.get("usar_domicilio_tarjeta") == "1"

        def _v(s): 
            return (s or "").strip()

        if usar_dom and t.bill_calle and t.bill_num_ext and t.bill_colonia and t.bill_municipio and t.bill_estado and t.bill_cp and t.bill_pais and t.bill_telefono:
            fact = {
                "nombre": datos_pago["nombre"],
                "rfc": datos_pago["rfc"],
                "calle": t.bill_calle,
                "num_ext": t.bill_num_ext,
                "num_int": t.bill_num_int or "",
                "colonia": t.bill_colonia,
                "municipio": t.bill_municipio,
                "estado": t.bill_estado,
                "cp": t.bill_cp,
                "pais": t.bill_pais,
                "telefono": t.bill_telefono,
            }
        else:
            # manual
            fact = {
                "nombre": datos_pago["nombre"],
                "rfc": datos_pago["rfc"],
                "calle": _v(request.form.get("calle")),
                "num_ext": _v(request.form.get("num_ext")),
                "num_int": _v(request.form.get("num_int")),
                "colonia": _v(request.form.get("colonia")),
                "municipio": _v(request.form.get("municipio")),
                "estado": _v(request.form.get("estado")),
                "cp": _v(request.form.get("cp")),
                "pais": _v(request.form.get("pais")) or "México",
                "telefono": _v(request.form.get("telefono")),
            }

        # Validación mínima si NO usó domicilio de tarjeta o está incompleto
        req_keys = ["calle","num_ext","colonia","municipio","estado","cp","pais","telefono"]
        if (not usar_dom) or any(not fact[k] for k in req_keys):
            # Si falta algo, rechaza (solo si el cliente quiso usar domicilio pero no estaba completo)
            if any(not fact[k] for k in req_keys):
                flash("Completa el domicilio de facturación (faltan datos).", "error")
                return render_template("pago.html", cart=cart_items_list(cart), total=total, fecha_hoy=fecha_hoy, guardadas=guardadas)

        nueva_orden = Orden(
            user_id=user.id,
            total=float(total),
            tarjeta_last4=t.numero[-4:],
            tarjeta_id=t.id,
            fact_nombre=fact["nombre"],
            fact_rfc=fact["rfc"],
            fact_calle=fact["calle"],
            fact_num_ext=fact["num_ext"],
            fact_num_int=fact["num_int"],
            fact_colonia=fact["colonia"],
            fact_municipio=fact["municipio"],
            fact_estado=fact["estado"],
            fact_cp=fact["cp"],
            fact_pais=fact["pais"],
            fact_telefono=fact["telefono"],
        )
        db.session.add(nueva_orden)
        db.session.flush()  # para tener nueva_orden.id

        # Guardar items
        for k, item in cart.items():
            prod = Producto.query.get(int(k))
            img = item.get("imagen") or ""
            db.session.add(OrdenItem(
                orden_id=nueva_orden.id,
                producto_id=prod.id if prod else int(k),
                nombre=item.get("nombre"),
                imagen=img,
                qty=int(item.get("qty")),
                precio_unit=float(item.get("precio")),
                specs=item.get("specs") or ""
            ))

        db.session.commit()
        session["last_order_id"] = nueva_orden.id

        # Guardar orden en sesión
        orden = {
            "items": cart_items_list(cart),
            "total": float(total),
            "usuario": session.get("user"),
            "tarjeta_id": t.id,
            "tarjeta_last4": t.numero[-4:],
            "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "datos_fiscales": datos_fiscales
        }
        session["orden"] = orden
        session["cart"] = {}
        return redirect(url_for("exito"))

    return render_template("pago.html", cart=cart_items_list(cart), total=total, fecha_hoy=fecha_hoy, guardadas=guardadas)


@app.route("/exito")
def exito():
    if "orden" not in session:
        return redirect(url_for("index"))
    return render_template("exito.html", orden=session["orden"])


@app.route("/descargar/<tipo>")
def descargar(tipo):
    o = session.get("orden")
    if not o:
        return redirect(url_for("index"))

    t = Tarjeta.query.get(o.get("tarjeta_id"))
    if not t:
        return redirect(url_for("index"))

    items = o["items"]
    total = o["total"]

    if tipo == "factura":
        return send_file(
            generar_pdf_factura(items, total, o["datos_fiscales"], t),
            as_attachment=True,
            download_name="Factura_LBV_DEMO.pdf"
        )

    return send_file(
        generar_pdf_recibo(items, total, o.get("usuario", "usuario")),
        as_attachment=True,
        download_name="Recibo_LBV_DEMO.pdf"
    )
@app.route("/historial")
def historial():
    if "user" not in session:
        return redirect(url_for("login"))

    perfil = usuario_actual()
    if not perfil:
        return redirect(url_for("logout"))

    ordenes = Orden.query.filter_by(user_id=perfil.id).order_by(Orden.fecha.desc()).all()
    return render_template("historial.html", ordenes=ordenes)
@app.route("/orden/<int:orden_id>/factura")
def factura_orden(orden_id):
    if "user" not in session:
        return redirect(url_for("login"))

    perfil = usuario_actual()
    orden = Orden.query.get_or_404(orden_id)

    if orden.user_id != perfil.id:
        return redirect(url_for("historial"))

    items = []
    for it in orden.items:
        items.append({
            "nombre": it.nombre,
            "imagen": it.imagen,
            "qty": it.qty,
            "precio": it.precio_unit,
            "specs": it.specs
        })

    # perfil ficticio para usar tu función PDF (la factura se basa en fact_*)
    class PerfilTmp:
        pass

    p = PerfilTmp()
    p.id = perfil.id
    p.nombre = orden.fact_nombre
    p.rfc = orden.fact_rfc
    p.calle = orden.fact_calle
    p.num_ext = orden.fact_num_ext
    p.num_int = orden.fact_num_int
    p.colonia = orden.fact_colonia
    p.municipio = orden.fact_municipio
    p.estado = orden.fact_estado
    p.cp = orden.fact_cp
    p.pais = orden.fact_pais
    p.telefono = orden.fact_telefono

    tarjeta = Tarjeta.query.get(orden.tarjeta_id) if orden.tarjeta_id else None
    if not tarjeta:
        tarjeta = Tarjeta(numero="000000000000" + orden.tarjeta_last4, nombre_titular="", rfc="", fecha_expiracion="01/30", cvv="", intentos=0, fondos=0, verificada=True)

    return send_file(
        generar_pdf_factura(items, orden.total, p, tarjeta),
        as_attachment=True,
        download_name=f"factura_orden_{orden.id}.pdf"
    )


@app.route("/orden/<int:orden_id>/recibo")
def recibo_orden(orden_id):
    if "user" not in session:
        return redirect(url_for("login"))

    perfil = usuario_actual()
    orden = Orden.query.get_or_404(orden_id)

    if orden.user_id != perfil.id:
        return redirect(url_for("historial"))

    items = []
    for it in orden.items:
        items.append({
            "nombre": it.nombre,
            "imagen": it.imagen,
            "qty": it.qty,
            "precio": it.precio_unit,
            "specs": it.specs
        })

    class PerfilTmp:
        pass

    p = PerfilTmp()
    p.nombre = orden.fact_nombre
    p.rfc = orden.fact_rfc
    p.telefono = orden.fact_telefono

    return send_file(
        generar_pdf_recibo(items, orden.total, p),
        as_attachment=True,
        download_name=f"recibo_orden_{orden.id}.pdf"
    )


if __name__ == "__main__":
    inicializar_db()
    app.run(debug=True)
