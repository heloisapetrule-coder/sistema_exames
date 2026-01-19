from flask import Flask, render_template, request, redirect, url_for, session, send_file
from supabase import create_client
from datetime import date, datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os
import io

# ===============================
# CONFIGURAÇÃO APP
# ===============================
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")  # Necessário para sessão login

# ===============================
# CONFIGURAÇÃO SUPABASE
# ===============================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ===============================
# ROTAS DE LOGIN
# ===============================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]

        usuario = supabase.table("usuarios").select("*").eq("email", email).eq("senha", senha).execute().data
        if usuario:
            session["usuario_id"] = usuario[0]["id"]
            session["usuario_nome"] = usuario[0]["nome"]
            return redirect(url_for("index"))
        else:
            return render_template("login.html", erro="Email ou senha inválidos")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ===============================
# HOME - EXAMES DO DIA
# ===============================
@app.route("/")
def index():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    hoje = date.today().isoformat()
    exames = supabase.table("exames").select("*")\
        .eq("criado_por", session["usuario_id"])\
        .eq("data", hoje)\
        .order("criado_em", desc=True).execute().data
    return render_template("index.html", exames=exames, hoje=hoje)

# ===============================
# CADASTRAR EXAME
# ===============================
@app.route("/cadastrar", methods=["POST"])
def cadastrar():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    dados = {
        "nome": request.form["nome"],
        "cpf": request.form["cpf"],
        "empresa": request.form.get("empresa"),
        "planta": request.form.get("planta"),
        "exame": request.form["exame"],
        "status": "Em espera",
        "data": request.form.get("data") or date.today().isoformat(),
        "criado_por": session["usuario_id"]
    }
    supabase.table("exames").insert(dados).execute()
    return redirect(url_for("index"))

# ===============================
# ALTERAR STATUS
# ===============================
@app.route("/status/<id>/<novo_status>")
def alterar_status(id, novo_status):
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    supabase.table("exames").update({"status": novo_status}).eq("id", id).execute()
    return redirect(url_for("index"))

# ===============================
# EXAMES ARQUIVADOS (POR DATA)
# ===============================
@app.route("/arquivados")
def arquivados():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    data_busca = request.args.get("data")
    query = supabase.table("exames").select("*").eq("criado_por", session["usuario_id"])

    if data_busca:
        query = query.eq("data", data_busca)

    exames = query.order("criado_em", desc=True).execute().data
    return render_template("arquivados.html", exames=exames, data_busca=data_busca)

# ===============================
# PESQUISAR EXAMES (NOME / CPF / DATA)
# ===============================
@app.route("/pesquisar", methods=["GET", "POST"])
def pesquisar():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    termo = request.form.get("termo", "")
    query = supabase.table("exames").select("*").eq("criado_por", session["usuario_id"])
    if termo:
        query = query.or_(f"nome.ilike.%{termo}%,cpf.ilike.%{termo}%")

    exames = query.order("criado_em", desc=True).execute().data
    return render_template("index.html", exames=exames, hoje=date.today().isoformat(), termo=termo)

# ===============================
# GERAR PDF
# ===============================
@app.route("/pdf/<id>")
def gerar_pdf(id):
    exame = supabase.table("exames").select("*").eq("id", id).single().execute().data
    if not exame:
        return "Exame não encontrado", 404

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, altura - 50, "Controle de Exames - GASEO Limeira")

    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, altura - 100, f"Nome: {exame['nome']}")
    pdf.drawString(50, altura - 120, f"CPF: {exame['cpf']}")
    pdf.drawString(50, altura - 140, f"Empresa: {exame.get('empresa','-')}")
    pdf.drawString(50, altura - 160, f"Exame: {exame['exame']}")
    pdf.drawString(50, altura - 180, f"Planta: {exame.get('planta','-')}")
    pdf.drawString(50, altura - 200, f"Status: {exame['status']}")
    pdf.drawString(50, altura - 220, f"Data: {exame['data']}")

    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawString(50, 40, f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name=f"exame_{exame['nome']}.pdf", mimetype="application/pdf")

# ===============================
# RODAR APP
# ===============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)