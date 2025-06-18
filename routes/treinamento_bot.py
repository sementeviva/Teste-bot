from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from psycopg2.extras import RealDictCursor
import json

from utils.db_utils import get_db_connection

treinamento_bot_bp = Blueprint('treinamento_bot_bp', __name__, template_folder='../templates')

@treinamento_bot_bp.route('/', methods=['GET', 'POST'])
@login_required
def treinamento():
    """
    Exibe a página de treinamento e salva as configurações do bot
    para a conta do utilizador atualmente logado.
    """
    conta_id_logada = current_user.conta_id
    conn = get_db_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if request.method == 'POST':
                # --- LÓGICA PARA SALVAR OS DADOS ---
                # Obtém todos os dados do formulário
                configuracoes = {
                    'nome_loja_publico': request.form.get('nome_loja_publico'),
                    'horario_funcionamento': request.form.get('horario_funcionamento'),
                    'endereco': request.form.get('endereco'),
                    'link_google_maps': request.form.get('link_google_maps'),
                    'nome_assistente': request.form.get('nome_assistente'),
                    'tom_de_voz': request.form.get('tom_de_voz'),
                    'saudacao_personalizada': request.form.get('saudacao_personalizada'),
                    'despedida_personalizada': request.form.get('despedida_personalizada'),
                    'usar_emojis': 'usar_emojis' in request.form,
                    'faq_conhecimento': request.form.get('faq_conhecimento'),
                    'diretriz_principal_prompt': request.form.get('diretriz_principal_prompt'),
                    'conhecimento_especifico': request.form.get('conhecimento_especifico')
                }

                # A query de UPDATE usa a sintaxe 'ON CONFLICT' (UPSERT).
                # Se já existir uma configuração para a conta, ela atualiza (UPDATE).
                # Se não existir, ela insere (INSERT).
                cur.execute(
                    """
                    INSERT INTO configuracoes_bot (
                        conta_id, nome_loja_publico, horario_funcionamento, endereco, link_google_maps,
                        nome_assistente, tom_de_voz, saudacao_personalizada, despedida_personalizada, usar_emojis,
                        faq_conhecimento, diretriz_principal_prompt, conhecimento_especifico
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (conta_id) DO UPDATE SET
                        nome_loja_publico = EXCLUDED.nome_loja_publico,
                        horario_funcionamento = EXCLUDED.horario_funcionamento,
                        endereco = EXCLUDED.endereco,
                        link_google_maps = EXCLUDED.link_google_maps,
                        nome_assistente = EXCLUDED.nome_assistente,
                        tom_de_voz = EXCLUDED.tom_de_voz,
                        saudacao_personalizada = EXCLUDED.saudacao_personalizada,
                        despedida_personalizada = EXCLUDED.despedida_personalizada,
                        usar_emojis = EXCLUDED.usar_emojis,
                        faq_conhecimento = EXCLUDED.faq_conhecimento,
                        diretriz_principal_prompt = EXCLUDED.diretriz_principal_prompt,
                        conhecimento_especifico = EXCLUDED.conhecimento_especifico,
                        ultima_atualizacao = NOW()
                    """,
                    (
                        conta_id_logada, configuracoes['nome_loja_publico'], configuracoes['horario_funcionamento'], 
                        configuracoes['endereco'], configuracoes['link_google_maps'], configuracoes['nome_assistente'], 
                        configuracoes['tom_de_voz'], configuracoes['saudacao_personalizada'], 
                        configuracoes['despedida_personalizada'], configuracoes['usar_emojis'],
                        configuracoes['faq_conhecimento'], configuracoes['diretriz_principal_prompt'], 
                        configuracoes['conhecimento_especifico']
                    )
                )
                
                conn.commit()
                flash('Configurações salvas com sucesso!', 'success')
                return redirect(url_for('treinamento_bot_bp.treinamento'))

            # --- LÓGICA PARA EXIBIR A PÁGINA ---
            cur.execute("SELECT * FROM configuracoes_bot WHERE conta_id = %s", (conta_id_logada,))
            configuracoes = cur.fetchone()
            
            # Se for uma conta nova sem configurações, passa um dicionário vazio
            if not configuracoes:
                configuracoes = {}

    except Exception as e:
        flash(f'Ocorreu um erro: {e}', 'danger')
        print(f"Erro na página de treinamento para conta {conta_id_logada}: {e}")
        configuracoes = {} # Garante que a página não quebre em caso de erro
    finally:
        if conn:
            conn.close()

    return render_template('treinamento_bot.html', configuracoes=configuracoes)


