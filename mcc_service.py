import clr  # módulo principal do pythonnet
import os

# Adiciona uma referência a uma biblioteca padrão do .NET
clr.AddReference("System")
clr.AddReference(r"C:\\Users\\letic\\OneDrive\\Documentos\\sspce\\testando_pythonnet\\sdk\\Sdk\\MccSdk.dll")

from BioLab.Biometrics.Mcc.Sdk import MccSdk

def criar_indice_mcc(pasta_templates, arquivo_indice_saida, verbose=True):
    """
    Cria um índice MCC a partir de arquivos de template de minúcias.
    
    Args:
        pasta_templates: Caminho da pasta contendo arquivos .txt com minúcias
        arquivo_indice_saida: Caminho onde salvar o arquivo .idx
        verbose: Se True, mostra progresso detalhado
    
    Returns:
        tuple: (num_sucessos, num_erros, lista_erros)
    """
    
    # Parâmetros do índice MCC
    ns = 8              # número de setores
    nd = 6              # número de direções
    h = 24              # altura da célula
    l = 32              # largura da célula
    minNS = 30          # mínimo de células não vazias
    minNP = 2           # mínimo de pares
    deltaTheta = 3.14159 / 4.0  # tolerância angular
    deltaXY = 256       # tolerância espacial
    randomSeed = 17     # semente aleatória
    
    if verbose:
        print("🧠 Criando índice MCC...")
    
    MccSdk.CreateMccIndex(ns, nd, h, l, minNS, minNP, deltaTheta, deltaXY, randomSeed)
    
    if verbose:
        print("✅ Índice criado!\n")
    
    # Obtém lista de arquivos .txt
    todos_arquivos = sorted([f for f in os.listdir(pasta_templates) 
                            if f.lower().endswith('.txt')])
    
    if verbose:
        print(f"📁 Processando {len(todos_arquivos)} arquivos...\n")
    
    template_id = 0
    templates_adicionados = 0
    erros = []
    
    for i, arquivo in enumerate(todos_arquivos, 1):
        caminho_completo = os.path.join(pasta_templates, arquivo)
        caminho_absoluto = os.path.abspath(caminho_completo)
        
        if verbose:
            print(f"[{i:3d}/{len(todos_arquivos):3d}] {arquivo:35s} ", end='', flush=True)
        
        try:
            MccSdk.AddTextTemplateToMccIndex(caminho_absoluto, template_id)
            
            if verbose:
                print(f"✅ ID {template_id}")
            
            template_id += 1
            templates_adicionados += 1
            
        except Exception as e:
            if verbose:
                print(f"❌ {str(e)[:50]}")
            
            erros.append({
                'posicao': i,
                'arquivo': arquivo,
                'id': template_id,
                'erro': str(e)
            })
            template_id += 1
    
    # Salva índice
    if templates_adicionados > 0:
        if verbose:
            print(f"\n💾 Salvando índice...")
        
        MccSdk.SaveMccIndexToFile(arquivo_indice_saida)
        
        if verbose and os.path.exists(arquivo_indice_saida):
            tamanho = os.path.getsize(arquivo_indice_saida)
            print(f"✅ Índice salvo: {tamanho:,} bytes ({tamanho/1024:.1f} KB)")
            print(f"   📍 {arquivo_indice_saida}")
    
    # Limpa memória
    MccSdk.DeleteMccIndex()
    
    return templates_adicionados, len(erros), erros


def buscar_no_indice(arquivo_indice, arquivo_busca, max_candidatos=10):
    """
    Busca um template no índice MCC (retorna IDs e scores).
    
    Args:
        arquivo_indice: Caminho do arquivo .idx
        arquivo_busca: Caminho do arquivo .txt com minúcias para buscar
        max_candidatos: Número máximo de candidatos a retornar
    
    Returns:
        list: Lista de dicts {'id': int, 'score': float, 'rank': int}
    """
    
    # Carrega índice
    MccSdk.LoadMccIndexFromFile(arquivo_indice)
    
    try:
        # Busca - retorna TUPLA (candidateList, sortedSimilarities)
        resultado = MccSdk.SearchTextTemplateIntoMccIndex(
            arquivo_busca,
            False  # False = otimizado top-N
        )
        
        # Desempacota a tupla
        if isinstance(resultado, tuple) and len(resultado) == 2:
            candidateList, sortedSimilarities = resultado
        else:
            candidateList = resultado
            sortedSimilarities = None
        
        # Se não encontrou candidatos
        if candidateList is None or len(candidateList) == 0:
            return []
        
        # Converte para lista Python
        resultados = []
        for i in range(min(len(candidateList), max_candidatos)):
            candidate_id = int(candidateList[i])
            score = float(sortedSimilarities[i]) if sortedSimilarities is not None else None
            
            resultado_item = {
                'id': candidate_id,
                'rank': i + 1
            }
            
            if score is not None:
                resultado_item['score'] = score
            
            resultados.append(resultado_item)
        
        return resultados
        
    except Exception as e:
        print(f"❌ Erro na busca: {e}")
        import traceback
        traceback.print_exc()
        return []
    
    finally:
        # Limpa índice da memória
        try:
            MccSdk.DeleteMccIndex()
        except:
            pass


def buscar_e_comparar(arquivo_indice, arquivo_busca, pasta_templates, max_candidatos=5):
    """
    Busca no índice COM scores (usa os scores retornados pela busca).
    
    Args:
        arquivo_indice: Caminho do .idx
        arquivo_busca: Template para buscar
        pasta_templates: Pasta com os templates originais
        max_candidatos: Top-N candidatos
    
    Returns:
        list: Lista de dicts {'id': int, 'score': float, 'arquivo': str, 'rank': int}
    """
    
    # Carrega índice
    MccSdk.LoadMccIndexFromFile(arquivo_indice)
    
    try:
        # Busca - retorna TUPLA (candidateList, sortedSimilarities)
        resultado = MccSdk.SearchTextTemplateIntoMccIndex(
            arquivo_busca,
            False  # False = otimizado top-N
        )
        
        # Desempacota a tupla
        if isinstance(resultado, tuple) and len(resultado) == 2:
            candidateList, sortedSimilarities = resultado
        else:
            print("❌ Formato de retorno inesperado")
            return []
        
        # Se não encontrou candidatos
        if candidateList is None or len(candidateList) == 0:
            return []
        
        # Obtém lista de arquivos (mesma ordem usada na indexação)
        arquivos = sorted([f for f in os.listdir(pasta_templates) if f.lower().endswith('.txt')])
        
        # Monta resultados com scores
        resultados = []
        for i in range(min(len(candidateList), max_candidatos)):
            candidate_id = int(candidateList[i])
            score = float(sortedSimilarities[i])
            
            # Obtém nome do arquivo
            arquivo_nome = arquivos[candidate_id] if candidate_id < len(arquivos) else f"ID_{candidate_id}"
            
            resultados.append({
                'id': candidate_id,
                'score': score,
                'arquivo': arquivo_nome,
                'rank': i + 1
            })
        
        return resultados
        
    except Exception as e:
        print(f"❌ Erro na busca: {e}")
        import traceback
        traceback.print_exc()
        return []
    
    finally:
        # Limpa índice da memória
        try:
            MccSdk.DeleteMccIndex()
        except:
            pass


def buscar_com_politicas(arquivo_indice, arquivo_busca, pasta_templates,
                         limiar_match=0.80,
                         limiar_ambiguidade=0.10,
                         max_candidatos=10):
    """
    Busca com políticas de decisão configuráveis.
    
    Args:
        arquivo_indice: Caminho do .idx
        arquivo_busca: Template para buscar
        pasta_templates: Pasta com templates originais
        limiar_match: Score mínimo para considerar match
        limiar_ambiguidade: Diferença mínima entre top-1 e top-2
        max_candidatos: Número máximo de candidatos
    
    Returns:
        dict: Resultado com status, id, score, candidatos e mensagem
    """
    
    # Busca com scores
    candidatos = buscar_e_comparar(arquivo_indice, arquivo_busca, pasta_templates, max_candidatos)
    
    resultado = {
        'status': None,
        'id': None,
        'score': None,
        'candidatos': candidatos,
        'mensagem': ''
    }
    
    if len(candidatos) == 0:
        resultado['status'] = 'NAO_ENCONTRADO'
        resultado['mensagem'] = 'Nenhum candidato no índice'
        return resultado
    
    # Top candidato
    top = candidatos[0]
    top_score = top['score']
    
    # Abaixo do limiar
    if top_score < limiar_match:
        resultado['status'] = 'ABAIXO_LIMIAR'
        resultado['score'] = top_score
        resultado['mensagem'] = f'Score {top_score:.3f} < limiar {limiar_match}'
        return resultado
    
    # Verifica ambiguidade
    if len(candidatos) > 1:
        segundo_score = candidatos[1]['score']
        diferenca = top_score - segundo_score
        
        if diferenca < limiar_ambiguidade:
            resultado['status'] = 'AMBIGUO'
            resultado['mensagem'] = (f'Ambíguo: {top_score:.3f} vs '
                                    f'{segundo_score:.3f} (diff={diferenca:.3f})')
            return resultado
    
    # Match positivo
    resultado['status'] = 'MATCH'
    resultado['id'] = top['id']
    resultado['score'] = top_score
    resultado['mensagem'] = f'Match confirmado: score {top_score:.3f}'
    
    return resultado


# ============================================================================
# SCRIPT PRINCIPAL
# ============================================================================

if __name__ == "__main__":
    
    # Configurações
    pasta_templates = r'C:\Users\letic\OneDrive\Documentos\sspce\testando_pythonnet\templates\minutias_files'
    arquivo_idx = 'C:\\Users\\letic\\OneDrive\\Documentos\\sspce\\testando_pythonnet\\mcc_index.idx'
     
    print("="*70)
    print(" MCC SDK - Indexação de Templates Biométricos")
    print("="*70)
    print()
    
    # ========================================================================
    # ETAPA 1: INDEXAÇÃO
    # ========================================================================
    
    # Cria índice
    sucessos, erros_count, erros = criar_indice_mcc(pasta_templates, arquivo_idx)
    
    # Resumo
    print(f"\n{'='*70}")
    print(f"📊 Resumo da Indexação:")
    print(f"{'='*70}")
    print(f"   ✅ Templates indexados: {sucessos}")
    print(f"   ❌ Erros: {erros_count}")
    
    if erros_count > 0:
        print(f"\n⚠️ Arquivos com erro:")
        for erro in erros[:5]:  # Mostra até 5
            print(f"   - {erro['arquivo']}: {erro['erro'][:50]}")
        if erros_count > 5:
            print(f"   ... e mais {erros_count - 5} erros")
    
    print(f"\n✨ Indexação concluída!\n")
    
    # ========================================================================
    # ETAPA 2: BUSCA (EXEMPLOS)
    # ========================================================================
    
    if sucessos > 0:
        print("="*70)
        print(" Exemplos de Busca")
        print("="*70)
        print()
        
        # Arquivo de teste
        arquivo_teste = os.path.join(pasta_templates, '1148_S_04_F_A.txt')
        
        if os.path.exists(arquivo_teste):
            
            # --------------------------------------------------------------
            # EXEMPLO 1: Busca rápida (IDs e scores)
            # --------------------------------------------------------------
            print("🔍 EXEMPLO 1: Busca rápida (IDs e scores)")
            print(f"   Buscando: {os.path.basename(arquivo_teste)}\n")
            
            candidatos_rapidos = buscar_no_indice(arquivo_idx, arquivo_teste, max_candidatos=5)
            
            if candidatos_rapidos:
                print(f"   Top {len(candidatos_rapidos)} candidatos:")
                for c in candidatos_rapidos:
                    if 'score' in c:
                        print(f"      #{c['rank']}: ID {c['id']:3d} | Score: {c['score']:.4f}")
                    else:
                        print(f"      #{c['rank']}: ID {c['id']:3d}")
            else:
                print("   ❌ Nenhum candidato encontrado")
            
            print()
            
            # --------------------------------------------------------------
            # EXEMPLO 2: Busca com nomes de arquivos
            # --------------------------------------------------------------
            print("🔍 EXEMPLO 2: Busca com nomes de arquivos")
            print(f"   Buscando: {os.path.basename(arquivo_teste)}\n")
            
            resultados_scores = buscar_e_comparar(arquivo_idx, arquivo_teste, pasta_templates, max_candidatos=5)
            
            if resultados_scores:
                print(f"   Top {len(resultados_scores)} candidatos:")
                for r in resultados_scores:
                    print(f"      #{r['rank']}: ID {r['id']:3d} | Score: {r['score']:.4f} | {r['arquivo']}")
            else:
                print("   ❌ Nenhum candidato encontrado")
            
            print()
            
            # --------------------------------------------------------------
            # EXEMPLO 3: Busca com políticas de decisão
            # --------------------------------------------------------------
            print("🔍 EXEMPLO 3: Busca com políticas de decisão")
            print(f"   Buscando: {os.path.basename(arquivo_teste)}")
            print(f"   Limiar de match: 0.80")
            print(f"   Limiar de ambiguidade: 0.10\n")
            
            resultado = buscar_com_politicas(
                arquivo_idx, 
                arquivo_teste, 
                pasta_templates,
                limiar_match=0.80,
                limiar_ambiguidade=0.10,
                max_candidatos=10
            )
            
            print(f"   📊 Resultado:")
            print(f"      Status: {resultado['status']}")
            print(f"      Mensagem: {resultado['mensagem']}")
            
            if resultado['status'] == 'MATCH':
                print(f"      ✅ ID identificado: {resultado['id']}")
                print(f"      Score: {resultado['score']:.4f}")
            elif resultado['status'] == 'AMBIGUO':
                print(f"      ⚠️ Top candidatos ambíguos:")
                for i, c in enumerate(resultado['candidatos'][:3], 1):
                    print(f"         {i}. ID {c['id']} - Score: {c['score']:.4f}")
            
            print()
        else:
            print(f"⚠️ Arquivo de teste não encontrado: {arquivo_teste}")
    
    print("="*70)
    print(" Processamento completo!")
    print("="*70)
    print()