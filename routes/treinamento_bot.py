from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from psycopg2.extras import RealDictCursor
import json

from utils.db_utils import get_db_connection

treinamento_bot_bp = Blueprint('treinamento_bot_bp', __name__, template_folder='../templates')

@treinamento_bot_bp.route('/', methods=['GET', 'POST'])
@login_required
def treinamento():
    conta_id_logada = current_user.conta_id
    conn = get_db_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if request.method == 'POST':
                # --- INÍCIO DA NOVA LÓGICA PARA FAQ ---
                # Em vez de ler um textarea, obtemos duas listas: uma de perguntas, uma de respostas.
                faq_questions = request.form.getlist('faq_questions')
                faq_answers = request.form.getlist('faq_answers')

                # Combinamos as duas listas numa estrutura de dados que podemos guardar como JSON.
                # O 'zip' junta os pares. O 'if q and a' garante que não guardamos pares vazios.
                faq_list = [
                    {'question': q, 'answer': a} 
                    for q, a in zip(faq_questions, faq_answers) if q.strip() and a.strip()
                ]
                
                # Convertemos a lista de dicionários numa string JSON.
                # ensure_ascii=False é importante para guardar corretamente caracteres como 'ç' e 'ã'.
                faq_json_string = json.dumps(faq_list, ensure_ascii=False, indent=2)
                # --- FIM DA NOVA LÓGICA PARA FAQ ---

                configuracoes = {
                    'nome_loja_publico': request.form.get('nome_loja_publico'),
                    'horario_funcionamento': request.form.get('horario_funcionamento'),
                    'endereco': request.form.get('endereco'),
                    'link_google_maps': request.form.get('link_google_maps'),
                    'nome_assistente': request.form.get('nome_assistente'),
                    'saudacao_personalizada': request.form.get('saudacao_personalizada'),
                    'usar_emojis': 'usar_emojis' in request.form,
                    'faq_conhecimento': faq_json_string, # Guardamos a string JSON validada
                    'diretriz_principal_prompt': request.form.get('diretriz_principal_prompt'),
                    'conhecimento_especifico': request.form.get('conhecimento_especifico')
                }

                # A query de UPDATE/INSERT (UPSERT)
                cur.execute(
                    """
                    INSERT INTO configuracoes_bot (
                        conta_id, nome_loja_publico, horario_funcionamento, endereco, link_google_maps,
                        nome_assistente, saudacao_personalizada, usar_emojis, faq_conhecimento, 
                        diretriz_principal_prompt, conhecimento_especifico, ultima_atualizacao
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                    )
                    ON CONFLICT (conta_id) DO UPDATE SET
                        nome_loja_publico = EXCLUDED.nome_loja_publico,
                        horario_funcionamento = EXCLUDED.horario_funcionamento,
                        endereco = EXCLUDED.endereco,
                        link_google_maps = EXCLUDED.link_google_maps,
                        nome_assistente = EXCLUDED.nome_assistente,
                        saudacao_personalizada = EXCLUDED.saudacao_personalizada,
                        usar_emojis = EXCLUDED.usar_emojis,
                        faq_conhecimento = EXCLUDED.faq_conhecimento,
                        diretriz_principal_prompt = EXCLUDED.diretriz_principal_prompt,
                        conhecimento_especifico = EXCLUDED.conhecimento_especifico,
                        ultima_atualizacao = NOW()
                    """,
                    (
                        conta_id_logada, configuracoes['nome_loja_publico'], configuracoes['horario_funcionamento'], 
                        configuracoes['endereco'], configuracoes['link_google_maps'], configuracoes['nome_assistente'], 
                        configuracoes['saudacao_personalizada'], configuracoes['usar_emojis'],
                        configuracoes['faq_conhecimento'], configuracoes['diretriz_principal_prompt'], 
                        configuracoes['conhecimento_especifico']
                    )
                )
                
                conn.commit()
                flash('Configurações salvas com sucesso!', 'success')
                return redirect(url_for('treinamento_bot_bp.treinamento'))

            # Lógica para GET (exibir a página)
            cur.execute("SELECT * FROM configuracoes_bot WHERE conta_id = %s", (conta_id_logada,))
            configuracoes = cur.fetchone()
            
            if not configuracoes:
                configuracoes = {}
            else:
                # Se o FAQ existir, descodificamo-lo de JSON para uma lista Python
                # para que o nosso template a possa usar num loop.
                if configuracoes.get('faq_conhecimento'):
                    configuracoes['faq_list'] = json.loads(configuracoes['faq_conhecimento'])
                else:
                    configuracoes['faq_list'] = []

    except Exception as e:
        flash(f'Ocorreu um erro: {e}', 'danger')
        print(f"Erro na página de treinamento para conta {conta_id_logada}: {e}")
        configuracoes = {'faq_list': []}
    finally:
        if conn:
            conn.close()

    return render_template('treinamento_bot.html', configuracoes=configuracoes)


