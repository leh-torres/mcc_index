"""
MCC Matcher Service - Serviço Windows para busca de digitais similares
Integração: Flask (WSL) -> Docker (NBIS) -> Windows Service (MCC) -> Docker (NBIS/Bozorth)

FLUXO:
1. Flask envia o nome do arquivo probe
2. MCC Service busca na pasta de templates
3. Retorna top-5 nomes de arquivos similares + scores
"""

import clr
import os
import time
from typing import Dict
from flask import Flask, request, jsonify
from flask_cors import CORS

clr.AddReference(r"C:\Users\letic\OneDrive\Documentos\sspce\testando_pythonnet\sdk\Sdk\MccSdk.dll")
from BioLab.Biometrics.Mcc.Sdk import MccSdk  # type: ignore

# ====================================================================
# CLASSE MCC MATCHER
# ====================================================================
class MccMatcherService:
    def __init__(self, pasta_templates: str, arquivo_indice: str):
        self.pasta_templates = pasta_templates
        self.arquivo_indice = arquivo_indice
        self.templates_map = {}
        self._carregar_mapeamento()

    def _carregar_mapeamento(self):
        arquivos = sorted([f for f in os.listdir(self.pasta_templates) if f.lower().endswith('.txt')])
        self.templates_map = {i: arq for i, arq in enumerate(arquivos)}
        print(f"📂 MCC Matcher carregou {len(self.templates_map)} templates.")

    def criar_indice(self, verbose: bool = True) -> Dict:
        inicio = time.time()
        if verbose:
            print("🔧 Criando índice MCC...")
        MccSdk.CreateMccIndex(8, 6, 24, 32, 30, 2, 3.14159/4.0, 256, 17)

        arquivos = sorted([f for f in os.listdir(self.pasta_templates) if f.lower().endswith('.txt')])
        sucessos, erros = 0, []
        for template_id, arquivo in enumerate(arquivos):
            caminho = os.path.join(self.pasta_templates, arquivo)
            try:
                MccSdk.AddTextTemplateToMccIndex(caminho, template_id)
                self.templates_map[template_id] = arquivo
                sucessos += 1
            except Exception as e:
                erros.append({'id': template_id, 'arquivo': arquivo, 'erro': str(e)})

        if sucessos > 0:
            MccSdk.SaveMccIndexToFile(self.arquivo_indice)
        MccSdk.DeleteMccIndex()
        print(f"✅ Índice MCC criado: {sucessos}/{len(arquivos)} templates.")
        return {'total': len(arquivos), 'sucessos': sucessos, 'erros': len(erros), 'tempo_segundos': time.time()-inicio}

    def buscar_similares(self, nome_probe: str, top_n: int = 5, score_minimo: float = 0.001) -> Dict:
        caminho_probe = os.path.join(self.pasta_templates, nome_probe)
        if not os.path.exists(caminho_probe):
            print(f"❌ Probe não encontrado: {caminho_probe}")
            return {'status': 'erro', 'mensagem': f'Arquivo não encontrado: {nome_probe}', 'candidatos': []}

        print(f"🔎 Iniciando busca MCC para: {nome_probe}")

        if not os.path.exists(self.arquivo_indice):
            print("❌ Índice MCC não encontrado. Execute setup primeiro.")
            return {'status': 'erro', 'mensagem': 'Índice não encontrado. Execute setup primeiro.', 'candidatos': []}

        tempo_inicio = time.time()
        MccSdk.LoadMccIndexFromFile(self.arquivo_indice)

        try:
            resultado = MccSdk.SearchTextTemplateIntoMccIndex(caminho_probe, False)
            candidateList, sortedSimilarities = resultado

            if not candidateList:
                print("⚠️ Nenhum candidato encontrado no MCC.")
                return {'status': 'sucesso', 'probe_arquivo': nome_probe, 'total_encontrados': 0, 'tempo_ms': (time.time()-tempo_inicio)*1000, 'candidatos': []}

            candidatos_validos = []
            for i in range(len(candidateList)):
                candidate_id = int(candidateList[i])
                score = float(sortedSimilarities[i])
                if score < score_minimo:
                    continue
                arquivo = self.templates_map.get(candidate_id, f'ID_{candidate_id}')
                candidatos_validos.append({'id': candidate_id, 'arquivo': arquivo, 'score': score})
                print(f"✅ Candidato encontrado: {arquivo} | Score MCC: {score}")

            candidatos_validos.sort(key=lambda x: x['score'], reverse=True)
            candidatos_json = [{'rank': r+1, 'arquivo': c['arquivo'], 'score_mcc': c['score']} for r, c in enumerate(candidatos_validos[:top_n])]

            print(f"📄 Retornando top-{len(candidatos_json)} candidatos para {nome_probe}")
            print(f"⏱️ Tempo total MCC: {round((time.time()-tempo_inicio)*1000, 2)} ms\n")

            return {'status': 'sucesso', 'probe_arquivo': nome_probe, 'total_encontrados': len(candidatos_validos), 'tempo_ms': (time.time()-tempo_inicio)*1000, 'candidatos': candidatos_json}

        except Exception as e:
            print(f"💥 Erro ao buscar similares MCC: {e}")
            return {'status': 'erro', 'mensagem': str(e), 'candidatos': []}

        finally:
            MccSdk.DeleteMccIndex()


# ====================================================================
# FLASK SERVICE
# ====================================================================
app = Flask(__name__)
CORS(app)

PASTA_TEMPLATES = r'C:\Users\letic\OneDrive\Documentos\sspce\testando_pythonnet\templates'
ARQUIVO_INDICE = r'C:\Users\letic\OneDrive\Documentos\sspce\testando_pythonnet\mcc_index.idx'

matcher = MccMatcherService(PASTA_TEMPLATES, ARQUIVO_INDICE)

@app.route('/health', methods=['GET'])
def health():
    return {'status': 'online', 'templates': len(matcher.templates_map), 'indice_existe': os.path.exists(ARQUIVO_INDICE)}

@app.route('/search', methods=['POST'])
def search():
    data = request.get_json()
    if not data or 'probe_file' not in data:
        return jsonify({'status': 'erro', 'mensagem': 'Campo "probe_file" obrigatório'}), 400

    nome_probe = data['probe_file']
    top_n = data.get('top_n', 5)
    score_minimo = data.get('score_minimo', 0.001)

    resultado = matcher.buscar_similares(nome_probe, top_n=top_n, score_minimo=score_minimo)
    return jsonify(resultado)

@app.route('/setup', methods=['POST'])
def setup():
    resultado = matcher.criar_indice(verbose=True)
    matcher._carregar_mapeamento()
    return jsonify({'status': 'sucesso', 'mensagem': 'Índice criado', 'estatisticas': resultado})

if __name__ == "__main__":
    if not os.path.exists(ARQUIVO_INDICE):
        matcher.criar_indice(verbose=True)
    app.run(host='0.0.0.0', port=5001, debug=False)