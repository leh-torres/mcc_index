import clr
import os
import time
import json
from typing import List, Dict
from dataclasses import dataclass

clr.AddReference(r"C:\Users\letic\OneDrive\Documentos\sspce\testando_pythonnet\sdk\Sdk\MccSdk.dll")

from BioLab.Biometrics.Mcc.Sdk import MccSdk  # type: ignore


# ============================================================================
# DATACLASS PARA RESULTADO
# ============================================================================

@dataclass
class CandidatoSimilar:
    """Representa um candidato similar encontrado na busca."""
    id: int
    arquivo: str
    caminho_completo: str
    score: float
    rank: int


# ============================================================================
# CLASSE PRINCIPAL - SIMPLIFICADA
# ============================================================================

class MccFingerprintMatcher:
    """
    Sistema SIMPLIFICADO de busca de impressões digitais usando MCC SDK.
    
    FUNCIONALIDADE:
    - Recebe arquivo de minúcias (formato MCC)
    - Retorna top-N candidatos mais similares da base indexada
    """
    
    def __init__(self, pasta_templates: str, arquivo_indice: str):
        """
        Inicializa o matcher.
        
        Args:
            pasta_templates: Pasta contendo templates da base
            arquivo_indice: Caminho do arquivo de índice (.idx)
        """
        self.pasta_templates = pasta_templates
        self.arquivo_indice = arquivo_indice
        self.templates_map = {}  # ID -> nome do arquivo
        
        # Parâmetros MCC (devem ser os mesmos usados na indexação)
        self.ns = 8
        self.nd = 6
        self.h = 24
        self.l = 32
        self.minNS = 30
        self.minNP = 2
        self.deltaTheta = 3.14159 / 4.0
        self.deltaXY = 256
        self.randomSeed = 17
    
    
    def criar_indice(self, verbose: bool = True) -> Dict:
        """
        Cria o índice MCC a partir dos templates na pasta.
        Executar APENAS UMA VEZ quando criar/atualizar a base.
        """
        inicio = time.time()
        
        if verbose:
            print("🔧 Criando índice MCC da base de templates...")
            print(f"   Pasta: {self.pasta_templates}")
        
        # Cria índice em memória
        MccSdk.CreateMccIndex(
            self.ns, self.nd, self.h, self.l, 
            self.minNS, self.minNP, 
            self.deltaTheta, self.deltaXY, 
            self.randomSeed
        )
        
        # Obtém todos os arquivos .txt da base
        arquivos = sorted([f for f in os.listdir(self.pasta_templates) 
                          if f.lower().endswith('.txt')])
        
        if verbose:
            print(f"📁 Indexando {len(arquivos)} templates...\n")
        
        sucessos = 0
        erros = []
        
        for template_id, arquivo in enumerate(arquivos):
            caminho = os.path.abspath(os.path.join(self.pasta_templates, arquivo))
            
            if verbose:
                print(f"  [{template_id+1:4d}/{len(arquivos):4d}] {arquivo:45s} ", end='', flush=True)
            
            try:
                MccSdk.AddTextTemplateToMccIndex(caminho, template_id)
                self.templates_map[template_id] = arquivo
                
                if verbose:
                    print(f"✅")
                
                sucessos += 1
                
            except Exception as e:
                if verbose:
                    print(f"❌ {str(e)[:40]}")
                erros.append({'id': template_id, 'arquivo': arquivo, 'erro': str(e)})
        
        # Salva índice em disco
        if sucessos > 0:
            if verbose:
                print(f"\n💾 Salvando índice: {self.arquivo_indice}")
            
            MccSdk.SaveMccIndexToFile(self.arquivo_indice)
            
            if verbose:
                tamanho = os.path.getsize(self.arquivo_indice)
                print(f"✅ Índice salvo: {tamanho/1024/1024:.2f} MB\n")
        
        # Libera memória
        MccSdk.DeleteMccIndex()
        
        tempo_total = time.time() - inicio
        
        return {
            'total': len(arquivos),
            'sucessos': sucessos,
            'erros': len(erros),
            'tempo_segundos': tempo_total,
            'templates_map': self.templates_map.copy()
        }
    
    
    def carregar_mapeamento(self) -> int:
        """
        Carrega o mapeamento de IDs para nomes de arquivos.
        Deve ser chamado após criar o índice ou ao iniciar o sistema.
        
        Returns:
            int: Número de templates mapeados
        """
        arquivos = sorted([f for f in os.listdir(self.pasta_templates) 
                          if f.lower().endswith('.txt')])
        self.templates_map = {i: arq for i, arq in enumerate(arquivos)}
        return len(self.templates_map)
    
    
    def buscar_similares(self, arquivo_probe: str, 
                        top_n: int = 5,
                        score_minimo: float = 0.001,
                        verbose: bool = False) -> Dict:
        """
        ★ FUNÇÃO PRINCIPAL ★
        Busca os top-N candidatos mais similares ao probe.
        
        Args:
            arquivo_probe: Caminho do arquivo de minúcias (formato MCC)
            top_n: Número de candidatos para retornar
            score_minimo: Score mínimo para considerar (filtro)
            verbose: Mostrar logs
        
        Returns:
            dict: Resultado em formato JSON com lista de candidatos
        """
        
        if not os.path.exists(arquivo_probe):
            raise FileNotFoundError(f"Arquivo não encontrado: {arquivo_probe}")
        
        if not os.path.exists(self.arquivo_indice):
            raise FileNotFoundError(f"Índice não encontrado: {self.arquivo_indice}")
        
        if not self.templates_map:
            raise ValueError("Mapeamento vazio! Execute carregar_mapeamento() primeiro")
        
        tempo_inicio = time.time()
        
        # Carrega índice na memória
        MccSdk.LoadMccIndexFromFile(self.arquivo_indice)
        
        try:
            if verbose:
                print(f"🔍 Buscando similares para: {os.path.basename(arquivo_probe)}")
            
            # Busca no índice
            resultado = MccSdk.SearchTextTemplateIntoMccIndex(arquivo_probe, False)
            
            if not isinstance(resultado, tuple) or len(resultado) != 2:
                return []
            
            candidateList, sortedSimilarities = resultado
            
            if candidateList is None or len(candidateList) == 0:
                return []
            
            # Coleta TODOS os candidatos com score > score_minimo
            candidatos_validos = []
            
            for i in range(len(candidateList)):
                candidate_id = int(candidateList[i])
                score = float(sortedSimilarities[i])
                
                # Filtra por score mínimo
                if score < score_minimo:
                    continue
                
                arquivo = self.templates_map.get(candidate_id, f'ID_{candidate_id}')
                caminho = os.path.join(self.pasta_templates, arquivo)
                
                candidatos_validos.append({
                    'id': candidate_id,
                    'arquivo': arquivo,
                    'caminho': caminho,
                    'score': score
                })
            
            # Ordena por score (DECRESCENTE - maior primeiro)
            candidatos_validos.sort(key=lambda x: x['score'], reverse=True)
            
            # Pega top-N e cria objetos CandidatoSimilar
            resultado_final = []
            for rank, cand in enumerate(candidatos_validos[:top_n], start=1):
                resultado_final.append(CandidatoSimilar(
                    id=cand['id'],
                    arquivo=cand['arquivo'],
                    caminho_completo=cand['caminho'],
                    score=cand['score'],
                    rank=rank
                ))
            
            tempo_total = (time.time() - tempo_inicio) * 1000  # ms
            
            if verbose:
                print(f"✅ Encontrados {len(candidatos_validos)} candidatos")
                print(f"⏱️  Tempo: {tempo_total:.1f}ms")
                print(f"\nTop {len(resultado_final)} candidatos:")
                for c in resultado_final:
                    print(f"   #{c.rank}: {c.arquivo:45s} | Score: {c.score:.4f}")
                print()
            
            return resultado_final
            
        finally:
            # Libera memória
            MccSdk.DeleteMccIndex()
    
    
    def buscar_similares_json(self, arquivo_probe: str, 
                             top_n: int = 5,
                             score_minimo: float = 0.001) -> Dict:
        """
        Versão que retorna resultado em formato JSON (para APIs REST).
        
        Returns:
            dict: Resultado serializável em JSON
        """
        try:
            tempo_inicio = time.time()
            
            candidatos = self.buscar_similares(
                arquivo_probe, 
                top_n=top_n, 
                score_minimo=score_minimo,
                verbose=False
            )
            
            tempo_total = (time.time() - tempo_inicio) * 1000
            
            return {
                'status': 'sucesso',
                'probe_arquivo': os.path.basename(arquivo_probe),
                'total_encontrados': len(candidatos),
                'tempo_ms': tempo_total,
                'candidatos': [
                    {
                        'rank': c.rank,
                        'id': c.id,
                        'arquivo': c.arquivo,
                        'caminho': c.caminho_completo,
                        'score': c.score
                    }
                    for c in candidatos
                ]
            }
            
        except Exception as e:
            return {
                'status': 'erro',
                'mensagem': str(e),
                'probe_arquivo': os.path.basename(arquivo_probe) if os.path.exists(arquivo_probe) else 'desconhecido',
                'candidatos': []
            }


# ============================================================================
# SCRIPT PRINCIPAL - EXEMPLO DE USO
# ============================================================================

if __name__ == "__main__":
    
    # Configurações
    pasta_templates = r'C:\Users\letic\OneDrive\Documentos\sspce\testando_pythonnet\templates'
    arquivo_indice = r'C:\Users\letic\OneDrive\Documentos\sspce\testando_pythonnet\mcc_index.idx'
    
    # Inicializa matcher
    matcher = MccFingerprintMatcher(pasta_templates, arquivo_indice)
    
    print("="*70)
    print(" SISTEMA DE BUSCA MCC - VERSÃO SIMPLIFICADA")
    print("="*70)
    print()
    
    # ========================================================================
    # SETUP: Criar índice (se não existir)
    # ========================================================================
    
    if not os.path.exists(arquivo_indice):
        print("⚙️  SETUP: Criando índice da base...\n")
        stats = matcher.criar_indice(verbose=True)
        print(f"✅ Índice criado: {stats['sucessos']}/{stats['total']} templates")
        print(f"⏱️  Tempo: {stats['tempo_segundos']:.2f}s\n")
    else:
        print(f"✅ Índice existente:")
        tamanho = os.path.getsize(arquivo_indice)
        print(f"   {os.path.basename(arquivo_indice)} ({tamanho/1024/1024:.2f} MB)")
        
        # Carrega mapeamento
        num_templates = matcher.carregar_mapeamento()
        print(f"   {num_templates} templates mapeados\n")
    
    # ========================================================================
    # EXEMPLO DE USO
    # ========================================================================
    
    arquivo_teste = r'C:\Users\letic\OneDrive\Documentos\sspce\testando_pythonnet\templates\0007_S_09_M_L.txt'
    
    if os.path.exists(arquivo_teste):
        
        print("="*70)
        print(" EXEMPLO: Busca de Similares")
        print("="*70)
        print()
        
        # ★ CHAMADA PRINCIPAL ★
        candidatos = matcher.buscar_similares(
            arquivo_probe=arquivo_teste,
            top_n=5,
            score_minimo=0.001,
            verbose=True
        )
        
        # Acessa os dados
        print("="*70)
        print(" RESULTADO")
        print("="*70)
        print()
        
        if candidatos:
            print(f"📊 Encontrados {len(candidatos)} candidatos similares:\n")
            
            for c in candidatos:
                print(f"Rank #{c.rank}:")
                print(f"   Arquivo: {c.arquivo}")
                print(f"   Caminho: {c.caminho_completo}")
                print(f"   Score:   {c.score:.4f}")
                print()
        else:
            print("❌ Nenhum candidato encontrado\n")
        
        # ====================================================================
        # FORMATO JSON (para APIs)
        # ====================================================================
        
        print("="*70)
        print(" FORMATO JSON")
        print("="*70)
        
        resultado_json = matcher.buscar_similares_json(arquivo_teste, top_n=5)
        with open("results_query.json", "w") as write_file:
            json.dumps(resultado_json, indent=2, ensure_ascii=False)
        print(json.dumps(resultado_json, indent=2, ensure_ascii=False))
        print()
    
    else:
        print(f"⚠️ Arquivo de teste não encontrado: {arquivo_teste}\n")
    
    # ========================================================================
    # RESUMO
    # ========================================================================
    
    print("="*70)
    print(" RESUMO")
    print("="*70)
    print()
    print("✅ Sistema pronto para uso!")
    print()
    print("📋 Uso básico:")
    print("   candidatos = matcher.buscar_similares(arquivo_probe, top_n=5)")
    print()
    print("📋 Para APIs REST:")
    print("   resultado = matcher.buscar_similares_json(arquivo_probe, top_n=5)")
    print()