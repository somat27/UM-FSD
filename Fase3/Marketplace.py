# ------------ Imports ------------ #
import json
import socket
import threading
import time
import psutil
import requests
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.x509 import load_pem_x509_certificate
from cryptography.exceptions import InvalidSignature
# ------------ Imports ------------ #

# ------------ Configuração Global ------------ #
COR_SUCESSO = '\033[92m' 
COR_ERRO = '\033[91m'    
COR_RESET = '\033[0m' 
COR_DEBUG = '\033[94m'
ARQUIVO_PRODUTORES = 'BasedeDados/Produtores.json'
subscricoes_compradas = {}
conexoes = {}
Lock = threading.RLock()
taxas_revenda = {}     
taxa_padrao = 10.0
DEBUG = False
# ------------ Configuração Global ------------ #

def debug(mensagem):
    if DEBUG:
        print(f"{COR_DEBUG}DEBUG: {COR_RESET}{mensagem}")
    
def exibir_erro(mensagem):
    print(f"{COR_ERRO}Erro: {COR_RESET}{mensagem}")
    
def exibir_sucesso(mensagem):
    print(f"{COR_SUCESSO}Sucesso: {COR_RESET}{mensagem}")

# ------------ Funções REST ------------ #
def ObterProdutoresRest():
    URL = "http://193.136.11.170:5001/produtor"
    try:
        response = requests.get(URL, timeout=2)
        produtores = response.json()

        for produtor in produtores:
            produtor['Conexao'] = "REST Seguro" if produtor.get('secure') == 1 else "REST Não Seguro"
        return produtores
    except requests.exceptions.RequestException as e:
        debug(f"Erro ao obter produtores REST: {e}")
        return []

def ObterCategoriasRest():
    CategoriasProdutorRestDisponiveis = []
    ProdutoresRest = ObterProdutoresRest()
    for ProdutorRest in ProdutoresRest:
        IP = ProdutorRest.get('ip')
        PORTA = ProdutorRest.get('porta')
        Nome = ProdutorRest.get('nome')
        Conexao = ProdutorRest.get('Conexao', 'REST Desconhecido')

        if not IP or not PORTA:
            debug(f"Produtor inválido recebido do servidor central: {ProdutorRest}")
            continue

        if Conexao == "REST Seguro":
            Categorias = ObterCategoriasSegurasProdutorRest(IP, PORTA)
        else:
            Categorias = ObterCategoriasNaoSegurasProdutorRest(IP, PORTA)

        if Categorias:
            CategoriasProdutorRestDisponiveis.append({
                "Nome": Nome,
                "IP": IP,
                "PORTA": PORTA,
                "Conexao": Conexao,
                "Categorias": Categorias
            })
        else:
            debug(f"Produtor {Nome} ({IP}:{PORTA}) não retornou categorias válidas.")

    return CategoriasProdutorRestDisponiveis

def ObterCategoriasNaoSegurasProdutorRest(IP, PORTA):
    URL = f"http://{IP}:{PORTA}/categorias" 
    try:
        response = requests.get(URL, timeout=5) 
        if response.status_code == 200:
            return response.json()
        else:
            debug(f"Erro ao obter categorias não seguras de {IP}:{PORTA} - Status: {response.status_code}")
            return []
    except requests.exceptions.RequestException as e:
        debug(f"Erro ao ligar a {IP}:{PORTA} (Não Seguro): {e}")
        return []


def carregar_certificado_gestor_do_ficheiro():
    with open("manager_public_key.pem", 'rb') as f:
        certificado_gestor_pem = f.read()
    return load_pem_public_key(certificado_gestor_pem)

def verificar_validade_certificado(certificado_produtor):
    certificado_produtor_pem = certificado_produtor.encode('utf-8')
    certificado_produtor_obj = load_pem_x509_certificate(certificado_produtor_pem)

    chave_publica_gestor = carregar_certificado_gestor_do_ficheiro()
    
    try:
        chave_publica_gestor.verify(
            certificado_produtor_obj.signature,
            certificado_produtor_obj.tbs_certificate_bytes,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        debug("Certificado do produtor é válido.")
    except Exception as e:
        debug(f"Falha na verificação do certificado do produtor: {e}")
        raise

def carregar_certificado_produtor(certificado_pem):
    return load_pem_x509_certificate(certificado_pem.encode('utf-8'))

def verificar_assinatura_resposta(certificado_produtor, assinatura, mensagem):
    certificado_produtor_obj = carregar_certificado_produtor(certificado_produtor)
    chave_publica_produtor = certificado_produtor_obj.public_key()
    
    assinatura_codificada = assinatura.encode('cp437')
    
    if isinstance(mensagem, list) or isinstance(mensagem, dict):
        mensagem = json.dumps(mensagem).encode('utf-8')
    elif isinstance(mensagem, str):
        mensagem = mensagem.encode('utf-8')

    try:
        chave_publica_produtor.verify(
            assinatura_codificada,
            mensagem,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        debug("Assinatura da resposta é válida.")
    except InvalidSignature:
        return False
    except Exception as e:
        debug(f"Falha na verificação da assinatura. Tipo do Erro: {type(e)}")
        debug(f"Detalhes do Erro: {repr(e)}")
        return False
    return True

def ObterCategoriasSegurasProdutorRest(IP, PORTA):
    URL = f"http://{IP}:{PORTA}/secure/categorias"
    try:
        response = requests.get(URL, timeout=5)
        if response.status_code == 200:
            try:
                dados = response.json()
            except ValueError as e:
                debug(f"Erro ao decodificar JSON: {e}")
                return []
            if dados and "mensagem" in dados and "assinatura" in dados and "certificado" in dados:
                assinatura = dados["assinatura"]
                certificado = dados["certificado"]
                
                verificar_validade_certificado(certificado)
                if verificar_assinatura_resposta(certificado, assinatura, dados["mensagem"]):
                    return dados["mensagem"]
                else:
                    debug("Assinatura inválida!")
                    return []
            else:
                debug(f"Estrutura de resposta inesperada: {dados}")
                return []
        else:
            debug(f"Erro ao obter categorias: {response.status_code}")
            return []
    except requests.exceptions.RequestException as e:
        return []
    
def ObterProdutosNaoSegurosPorCategoria(IP, PORTA, categoria):
    URL = f"http://{IP}:{PORTA}/produtos?categoria={categoria}"
    try:
        response = requests.get(URL, timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            debug(f"Erro ao obter produtos não seguros de {IP}:{PORTA} - Status: {response.status_code}")
            return []
    except requests.exceptions.RequestException as e:
        debug(f"Erro ao ligar a {IP}:{PORTA} para obter produtos (Não Seguro): {e}")
        return []


def ObterProdutosSegurosPorCategoria(IP, PORTA, categoria):
    URL = f"http://{IP}:{PORTA}/secure/produtos?categoria={categoria}"
    try:
        response = requests.get(URL, timeout=5)
        if response.status_code == 200:
            try:
                dados = response.json()
            except ValueError as e:
                debug(f"Erro ao decodificar JSON: {e}")
                return []
            if dados and "mensagem" in dados and "assinatura" in dados and "certificado" in dados:
                assinatura = dados["assinatura"]
                certificado = dados["certificado"]
                
                verificar_validade_certificado(certificado)
                if verificar_assinatura_resposta(certificado, assinatura, dados["mensagem"]):
                    return dados["mensagem"]
                else:
                    debug("Assinatura inválida!")
                    return []
            else:
                debug(f"Estrutura de resposta inesperada: {dados}")
                return []
        else:
            debug(f"Erro ao obter categorias: {response.status_code}")
            return []
    except requests.exceptions.RequestException as e:
        return []
    
def ComprarProdutoNaoSeguro(IP, PORTA, produto, quantidade):
    URL = f"http://{IP}:{PORTA}/comprar/{produto}/{quantidade}"
    try:
        response = requests.get(URL, timeout=5)
        if response.status_code == 200:
            debug(f"Compra de {quantidade} unidade(s) de {produto} concluída com sucesso.")
            return True
        elif response.status_code == 404:
            debug(f"Erro: Produto {produto} não encontrado ou quantidade insuficiente.")
        else:
            debug(f"Erro ao comprar o produto {produto}: {response.status_code}")
    except requests.exceptions.RequestException as e:
        debug(f"Erro a ligar ao {IP}:{PORTA} para comprar produto.: {e}")
    return False


def ComprarProdutoSeguro(IP, PORTA, produto, quantidade):
    URL = f"http://{IP}:{PORTA}/secure/comprar/{produto}/{quantidade}"
    try:
        response = requests.post(URL, timeout=5)
        if response.status_code == 200:
            try:
                dados = response.json()
            except ValueError as e:
                debug(f"Erro ao decodificar JSON: {e}")
                return False
            if dados and "mensagem" in dados and "assinatura" in dados and "certificado" in dados:
                assinatura = dados["assinatura"]
                certificado = dados["certificado"]

                verificar_validade_certificado(certificado)
                if verificar_assinatura_resposta(certificado, assinatura, dados["mensagem"]):
                    debug(f"{COR_SUCESSO}Sucesso: {COR_RESET}{dados['mensagem']}")
                    return True
                else:
                    debug(f"{COR_ERRO}Erro: {COR_RESET}Assinatura inválida na resposta!")
            else:
                debug(f"Estrutura de resposta inesperada: {dados}")
        else:
            debug(f"{COR_ERRO}Erro: {COR_RESET}Erro ao comprar: {response.status_code}")
    except requests.exceptions.RequestException as e:
        debug(f"{COR_ERRO}Erro: {COR_RESET}Erro ao ligar ao produtor REST: {e}")
    return False
# ------------ Funções REST ------------ #

# ------------ Funções Socket ------------ #
def ObterProdutoresSocket():
    ProdutoresSocketAtivos = []
    with open(ARQUIVO_PRODUTORES, 'r') as arquivo:
        ArquivoProdutores = json.load(arquivo)
    for ProdutorSocket in ArquivoProdutores:
        ip = ProdutorSocket['IP']
        porta = ProdutorSocket['Porta']
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                resultado = s.connect_ex((ip, porta))
                if resultado == 0:
                    ProdutoresSocketAtivos.append(ProdutorSocket)
        except Exception as e:
            debug(f"Erro ao testar conexão com {ip}:{porta}: {e}")
    return ProdutoresSocketAtivos

def ObterCategoriasSocket():
    CategoriasProdutorSocketDisponiveis = []
    ProdutoresSocketAtivos = ObterProdutoresSocket()
    for ProdutorSocket in ProdutoresSocketAtivos:
        IP = ProdutorSocket['IP']
        PORTA = ProdutorSocket['Porta']
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                s.connect((IP, PORTA))
                s.sendall("LISTAR_CATEGORIAS".encode('utf-8'))
                data = s.recv(1024).decode()
                categorias = data.split("\n")[1:]
                if categorias:
                    CategoriasProdutorSocketDisponiveis.append({
                        "Nome": ProdutorSocket['Nome'],
                        "IP": IP,
                        "PORTA": PORTA,
                        "Conexao": "Socket",
                        "Categorias": categorias
                    })
                else:
                    exibir_erro(f"Nenhuma categoria encontrada para {ProdutorSocket['Nome']}")
        except Exception as e:
            debug(f"Erro ao ligar com {IP}:{PORTA} para obter categorias: {e}")
    return CategoriasProdutorSocketDisponiveis

def conectar_ao_produtor(ip, porta, nome_produtor):
    try:
        novo_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        novo_sock.connect((ip, porta))
        debug(f"Conexão estabelecida com o produtor {nome_produtor} ({ip}:{porta})")
        return novo_sock
    except socket.error as e:
        debug(f"Erro ao conectar com o produtor {nome_produtor} ({ip}:{porta}): {e}")
        return None

def verificar_conexao_periodicamente(sock, ip, porta, nome_produtor, timeout=30):
    falhas_consec = 0
    while falhas_consec * 2 < timeout:
        with Lock:
            try:
                sock.sendall(b"HEARTBEAT")
                resposta = sock.recv(1024).decode('utf-8')
                if resposta != "OK":
                    raise socket.error("Resposta inesperada do produtor")
                falhas_consec = 0  
            except socket.error:
                falhas_consec += 1
                print(f"Perda de conexão com o produtor {nome_produtor} ({ip}:{porta}) - tentativa {falhas_consec}")
                novo_sock = conectar_ao_produtor(ip, porta, nome_produtor)
                if novo_sock:
                    print(f"Conexão restabelecida com o produtor {nome_produtor} ({ip}:{porta})")
                    sock.close()
                    sock = novo_sock
                    conexoes[(ip, porta)] = (sock, nome_produtor)
        time.sleep(2)
    
    print(f"Produtor {nome_produtor} ({ip}:{porta}) desconectado por mais de {timeout} segundos. Removendo produtos.")
    remover_produtos_produtor(nome_produtor, ip, porta)

def remover_produtos_produtor(nome_produtor, ip, porta):
    global subscricoes_compradas, conexoes
    with Lock:
        if (ip, porta) in conexoes:
            del conexoes[(ip, porta)]
        if nome_produtor in subscricoes_compradas:
            del subscricoes_compradas[nome_produtor]
            debug(f"Produtos do produtor {nome_produtor} removidos devido à desconexão.")

def ComprarProdutoSocket(produtor_info, nome_produto, quantidade):
    ip = produtor_info['IP']
    porta = produtor_info['PORTA']
    nome_produtor = produtor_info['Nome']

    sock = conectar_ao_produtor(ip, porta, nome_produtor)
    if not sock:
        print(f"Não foi possível conectar ao produtor {nome_produtor} ({ip}:{porta}) para realizar a compra.")
        return False
    try:
        with sock:
            sock.settimeout(30)
            mensagem_compra = f"SUBSCREVER_PRODUTO,{nome_produto},{quantidade}"
            sock.sendall(mensagem_compra.encode('utf-8'))
            resposta = sock.recv(1024).decode('utf-8')
            if resposta == "OK":
                print(f"Compra concluída com sucesso para o produto {nome_produto} (Quantidade: {quantidade}).")
                # Atualizar subscrições compradas
                with Lock:
                    if nome_produtor not in subscricoes_compradas:
                        subscricoes_compradas[nome_produtor] = {
                            "ip": ip,
                            "porta": porta,
                            "produtos": []
                        }
                    subscricoes_compradas[nome_produtor]["produtos"].append({
                        "nome": nome_produto,
                        "quantidade": quantidade
                    })
                    conexoes[(ip, porta)] = (sock, nome_produtor)
                
                # Iniciar monitoramento após compra bem-sucedida
                threading.Thread(target=verificar_conexao_periodicamente, args=(sock, ip, porta, nome_produtor), daemon=True).start()
                return True
            else:
                debug(f"{COR_ERRO}Erro: {COR_RESET}Erro ao comprar {nome_produto}: {resposta}")
    except socket.timeout:
        debug(f"{COR_ERRO}Erro: {COR_RESET}Timeout atingido ao tentar ligar ao produtor {produtor_info['IP']}:{produtor_info['PORTA']}.")
    except Exception as e:
        debug(f"{COR_ERRO}Erro: {COR_RESET}Erro ao tentar comprar o produto {nome_produto}: {e}")
    return False
# ------------ Funções Socket ------------ #

# ------------ Funções Globais ------------ #
def obter_ip_vpn():
    for interface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and addr.address.startswith('10.'):
                return addr.address
    return None

def ObterProdutosPorCategoria(Produtor, CategoriaEscolhida):
    Produtos = []
    if Produtor['Conexao'] == "Socket":
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(10)
                try:
                    s.connect((Produtor['IP'], Produtor['PORTA']))
                    pedido = f"LISTAR_PRODUTOS_CATEGORIA,{CategoriaEscolhida}"
                    s.sendall(pedido.encode('utf-8'))
                    resposta = s.recv(4096).decode('utf-8')
                    Produtos = json.loads(resposta)
                except socket.timeout:
                    debug(f"Erro: Timeout atingido ao tentar ligar com o produtor {Produtor['IP']}:{Produtor['PORTA']}")
                except Exception as e:
                    debug(f"Erro inesperado ao tentar se ligar com o produtor: {e}")
        except Exception as e:
            debug(f"Erro ao se ligar ao produtor {Produtor['IP']}:{Produtor['PORTA']}. Detalhes: {e}")
        return Produtos
    elif Produtor['Conexao'] == "REST Seguro":
        Produtos = ObterProdutosSegurosPorCategoria(Produtor['IP'], Produtor['PORTA'], CategoriaEscolhida)
    elif Produtor['Conexao'] == "REST Não Seguro":
        Produtos = ObterProdutosNaoSegurosPorCategoria(Produtor['IP'], Produtor['PORTA'], CategoriaEscolhida)
    return Produtos
        
def ListarProdutos(ProdutosCategoriaEscolhida):
    print("\nProdutos disponíveis para compra:")
    produto_id = 1 
    for produtor_info in ProdutosCategoriaEscolhida:
        print(f"Produtor: {produtor_info['Nome']} ({produtor_info['IP']}:{produtor_info['PORTA']}) - Conexão: {produtor_info['Conexao']}")
        for produto in produtor_info['Produtos']:
            print(f"{produto_id}. Produto: {produto['produto']} - Preço: {produto['preco']} - Quantidade disponível: {produto['quantidade']}")
            produto_id += 1 

def ComprarProdutos(ProdutosCategoriaEscolhida, produtos_escolhidos):
    produto_id = 1
    produtos_para_exibir = []

    for produtor_info in ProdutosCategoriaEscolhida:
        for produto in produtor_info['Produtos']:
            produto['id'] = produto_id
            produtos_para_exibir.append({"produto": produto, "produtor": produtor_info})
            produto_id += 1

    for id_produto in produtos_escolhidos:
        produto_encontrado = next((p for p in produtos_para_exibir if p["produto"]['id'] == id_produto), None)
        if not produto_encontrado:
            exibir_erro(f"Produto com ID {id_produto} não encontrado.")
            continue

        produto = produto_encontrado["produto"]
        produtor_info = produto_encontrado["produtor"]

        if produto['quantidade'] == 0:
            exibir_erro(f"Desculpe, {produto['produto']} está fora de estoque.")
            continue

        try:
            quantidade_desejada = int(input(f"Quantas unidades de {produto['produto']} deseja comprar? "))
            if quantidade_desejada <= 0:
                exibir_erro("Quantidade inválida. Insira um número positivo.")
                continue

            if quantidade_desejada <= produto['quantidade']:
                sucesso = False
                
                if produtor_info['Conexao'] == 'Socket':
                    sucesso = ComprarProdutoSocket(produtor_info, produto['produto'], quantidade_desejada)
                elif produtor_info['Conexao'] == 'REST Seguro':
                    sucesso = ComprarProdutoSeguro(produtor_info['IP'], produtor_info['PORTA'], produto['produto'], quantidade_desejada)
                elif produtor_info['Conexao'] == 'REST Não Seguro':
                    sucesso = ComprarProdutoNaoSeguro(produtor_info['IP'], produtor_info['PORTA'], produto['produto'], quantidade_desejada)

                if sucesso:
                    produto['quantidade'] -= quantidade_desejada

                    nome_produtor = produtor_info["Nome"]
                    ip = produtor_info["IP"]
                    porta = produtor_info["PORTA"]
                    conexao = produtor_info["Conexao"]

                    if nome_produtor not in subscricoes_compradas:
                        subscricoes_compradas[nome_produtor] = {
                            "ip": ip,
                            "porta": porta,
                            "conexao": conexao,
                            "produtos": []
                        }

                    produto_existente = next(
                        (p for p in subscricoes_compradas[nome_produtor]["produtos"] if p["nome"] == produto['produto']), None
                    )

                    if produto_existente:
                        produto_existente["quantidade"] += quantidade_desejada
                    else:
                        subscricoes_compradas[nome_produtor]["produtos"].append({
                            "nome": produto['produto'],
                            "quantidade": quantidade_desejada,
                            "preco": produto['preco']
                        })

                    exibir_sucesso(f"{quantidade_desejada} unidades de {produto['produto']} compradas com sucesso.")
                else:
                    exibir_erro(f"Falha ao comprar {quantidade_desejada} unidades de {produto['produto']}.")
            else:
                exibir_erro(f"Desculpe, só temos {produto['quantidade']} unidades disponíveis de {produto['produto']}.")
        except ValueError:
            debug("Quantidade inválida. Insira um número válido.")

def listar_subscricoes():
    if not subscricoes_compradas:
        exibir_erro(f"Não tem nenhuma subscrição.")
        return
    print("--- Subscrições Ativas ---")
    for nome_produtor, dados_produtor in subscricoes_compradas.items():
        ip = dados_produtor["ip"]
        porta = dados_produtor["porta"]
        conexao = dados_produtor["conexao"]
        print(f"Produtor: {nome_produtor} (IP: {ip}, Porta: {porta}, Conexão: {conexao})")
        for produto in dados_produtor["produtos"]:
            nome_produto = produto["nome"]
            quantidade = produto["quantidade"]
            preco_compra = float(produto["preco"])
            taxa_revenda = float(taxas_revenda.get(nome_produto, taxa_padrao))
            preco_Com_taxa= round(preco_compra * taxa_revenda, 2)
            preco_venda = preco_compra + (preco_Com_taxa / 100)
            print(f" - {nome_produto} - Quantidade: {quantidade}")
            print(f"\tPreço de Venda: {preco_venda:.2f}€ ( Preço de Compra: {preco_compra:.2f}€ | Taxa de Revenda: {taxa_revenda}%)")

def definir_taxa_revenda():
    try:
        print("\n--- Definir Taxa de Revenda ---")
        print("\nProdutos disponíveis:")
        produto_id = 1
        produtos_para_exibir = []
        for produtor_info in subscricoes_compradas.values():
            for produto in produtor_info["produtos"]:
                print(f"{produto_id}. Produto: {produto['nome']} - Preço de Compra: {produto['preco']}")
                produtos_para_exibir.append(produto)
                produto_id += 1
        produto_numero = int(input("\nIntroduza o número do produto para definir a taxa de revenda: "))
        if produto_numero < 1 or produto_numero > len(produtos_para_exibir):
            exibir_erro(f"Número de produto inválido.")
            return
        produto_selecionado = produtos_para_exibir[produto_numero - 1]
        print(f"Selecionou o produto: {produto_selecionado['nome']}")
        taxa = float(input("Introduza a nova taxa de revenda (%): "))
        if taxa < 0:
            exibir_erro(f"A taxa não pode ser negativa.")
            return
        taxas_revenda[produto_selecionado['nome']] = taxa
        exibir_sucesso(f"Taxa de revenda para o produto '{produto_selecionado['nome']}' definida para {taxa}%.")
    except ValueError:
        debug(f"{COR_ERRO}Erro: {COR_RESET}Valor inválido. Insira um número válido.")

def MenuMarketplace():
    while True:
        print("--- Menu Marketplace ---")
        print("1. Subscrições Ativas")
        print("2. Comprar Produtos")
        print("3. Definir Taxa de Revenda")
        print("99. Sair")
        escolha = input("Escolha uma opção: ")
        if escolha == '1':
            listar_subscricoes()
        elif escolha == '2':
            main()
        elif escolha == '3':
            definir_taxa_revenda()
        elif escolha == '99':
            exibir_sucesso(f"Saindo do Marketplace. Até logo!")
            time.sleep(1)
            break
        else:
            exibir_erro(f"Opção inválida. Tente novamente.")

def main():
    print("A carregar Categorias ...")
    ProdutoresComCategoriaEscolhida = []
    ProdutosCategoriaEscolhida = []
    CategoriasDisponiveis = set()
    
    CategoriasRest = ObterCategoriasRest()
    CategoriasSocket = ObterCategoriasSocket()
    Categorias = CategoriasRest + CategoriasSocket

    if Categorias:
        for Produtor in Categorias:
            print(f"{Produtor['Nome']} (IP: {Produtor['IP']}:{Produtor['PORTA']}) - {Produtor['Conexao']}")
            if 'Categorias' in Produtor and Produtor['Categorias']:
                for categoria in Produtor['Categorias']:
                    print(f" - {categoria}")
                CategoriasDisponiveis.update(Produtor['Categorias'])

        if CategoriasDisponiveis:
            print("\nCategorias Disponíveis:")
            print(", ".join(CategoriasDisponiveis))
        else:
            exibir_erro("\nSem categorias disponíveis. Tente novamente.")
            return
    
        while True:
            CategoriaEscolhida = input("\nEscolha uma categoria: ").strip()

            ProdutoresComCategoriaEscolhida = [
                Produtor for Produtor in Categorias 
                if 'Categorias' in Produtor and CategoriaEscolhida in Produtor['Categorias']
            ]

            if ProdutoresComCategoriaEscolhida:
                break 
            else:
                exibir_erro(f"A categoria '{CategoriaEscolhida}' não está disponível ou não possui produtos. Tente novamente.")
                
        for Produtor in ProdutoresComCategoriaEscolhida:
            Produtos = ObterProdutosPorCategoria(Produtor, CategoriaEscolhida)
            if Produtos:
                ProdutorComProdutos = {
                    'Nome': Produtor['Nome'],
                    'IP': Produtor['IP'],
                    'PORTA': Produtor['PORTA'],
                    'Conexao': Produtor['Conexao'],
                    'Produtos': Produtos
                }
                ProdutosCategoriaEscolhida.append(ProdutorComProdutos)

        if ProdutosCategoriaEscolhida:
            ListarProdutos(ProdutosCategoriaEscolhida)
            try:
                produtos_escolhidos = list(map(int, input("\nIntroduza os números dos produtos que deseja comprar (separados por vírgula): ").split(',')))
            except ValueError:
                debug("Entrada inválida. Insira números válidos separados por vírgula.")
                return

            ComprarProdutos(ProdutosCategoriaEscolhida, produtos_escolhidos)
            MenuMarketplace()
        else:
            exibir_erro(f"Sem produtos disponíveis na categoria '{CategoriaEscolhida}'. Tente novamente.")
    else:
        exibir_erro("Sem categorias disponíveis. Tente novamente.")
# ------------ Funções Globais ------------ #

if __name__ == "__main__":
    IP_Default = obter_ip_vpn()
    if IP_Default:
        exibir_sucesso(f"IP VPN detectado: {IP_Default}")
        main()
    else:
        exibir_erro(f"IP VPN não detectado, tente outra vez!")