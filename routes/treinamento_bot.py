# Teste-bot-main/routes/treinamento_bot.py

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from psycopg2.extras import RealDictCursor
import json

# ATUALIZADO: Importa a função que centraliza a lógica
from utils.db_utils import get_db_connection, get_bot_config

treinamento_bot_bp = Blueprint('treinamento_bot_bp', __name__, template_folder='../templates')

@treinamento_bot_bp.route('/', methods=['GET', 'POST'])
@login_required
def treinamento():
    conta_id_logada = current_user.conta_id
    conn = get_db_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if request.method == 'POST':
                # --- LÓGICA DE SALVAMENTO (POST) ---
                faq_questions = request.form.getlist('faq_questions')
                faq_answers = request.form.getlist('faq_answers')

                faq_list = [
                    {'question': q, 'answer': a} 
                    for q, a in zip(faq_questions, faq_answers) if q.strip() and a.strip()
                ]
                
                # Converte a lista de dicionários numa string JSON para salvar no banco.
                # O tipo de coluna 'jsonb' no PostgreSQL vai armazenar isso eficientemente.
                faq_json_string = json.dumps(faq_list, ensure_ascii=False, indent=2)

                # Monta um dicionário com todos os dados do formulário
                configuracoes_para_salvar = {
                    'nome_loja_publico': request.form.get('nome_loja_publico'),
                    'horario_funcionamento': request.form.get('horario_funcionamento'),
                    'endereco': request.form.get('endereco'),
                    'link_google_maps': request.form.get('link_google_maps'),
                    'nome_assistente': request.form.get('nome_assistente'),
                    'saudacao_personalizada': request.form.get('saudacao_personalizada'),
                    'usar_emojis': 'usar_emojis' in request.form,
                    'faq_conhecimento': faq_json_string,
                    'diretriz_principal_prompt': request.form.get('diretriz_principal_prompt'),
                    'conhecimento_especifico': request.form.get('conhecimento_especifico')
                }

                # Query de UPSERT (INSERT ... ON CONFLICT DO UPDATE)
                cur.execute(
                    """
                    INSERT INTO configuracoes_bot (
                        conta_id, nome_loja_publico, horario_funcionamento, endereco, link_google_maps,
                        nome_assistente, saudacao_personalizada, usar_emojis, faq_conhecimento, 
                        diretriz_principal_prompt, conhecimento_especifico, ultima_atualizacao
                    ) VALUES (
                        %(conta_id)s, %(nome_loja_publico)s, %(horario_funcionamento)s, %(endereco)s, %(link_google_maps)s,
                        %(nome_assistente)s, %(saudacao_personalizada)s, %(usar_emojis)s, %(faq_conhecimento)s,
                        %(diretriz_principal_prompt)s, %(conhecimento_especifico)s, NOW()
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
                    {
                        'conta_id': conta_id_logada,
                        **configuracoes_para_salvar # Desempacota o dicionário na query
                    }
                )
                
                conn.commit()
                flash('Configurações salvas com sucesso!', 'success')
                return redirect(url_for('treinamento_bot_bp.treinamento'))

            # --- CORREÇÃO DA LÓGICA DE EXIBIÇÃO (GET) ---
            # Em vez de fazer a query e a lógica de conversão aqui,
            # simplesmente chamamos a função get_bot_config que já faz tudo isso.
            configuracoes = get_bot_config(conta_id_logada)
            # A variável 'configuracoes' agora já contém a 'faq_list' processada
            # e valores padrão caso não exista configuração, evitando erros no template.

    except Exception as e:
        flash(f'Ocorreu um erro ao carregar a página de treinamento: {e}', 'danger')
        print(f"Erro na página de treinamento para conta {conta_id_logada}: {e}")
        # Em caso de erro, cria um dicionário vazio com a chave esperada pelo template
        # para evitar que a página quebre completamente.
        configuracoes = {'faq_list': []}
    finally:
        if conn:
            conn.close()

    return render_template('treinamento_bot.html', configuracoes=configuracoes)

