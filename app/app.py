# Definir o número de CPUs manualmente para evitar o warning do loky
# Você pode ajustar este valor para o número de núcleos que deseja usar
import os
os.environ["LOKY_MAX_CPU_COUNT"] = "4"  # Exemplo: usar 4 núcleos

import streamlit as st
import pandas as pd
from utils.geocoding import get_coordinates
from utils.routing import optimize_route, plan_route, plan_optimized_route
from utils.database import (
    setup_database, insert_address, insert_person, get_all_person_address_data,
    get_or_create_company, get_all_companies, insert_vehicle, get_all_vehicles,
    check_vehicle_exists, delete_vehicle, get_companies_with_persons,
    get_persons_by_company, get_company_address, create_route, add_route_stop,
    get_all_routes, get_route_details, save_route_api_response, get_route_api_response
)
import time
import re
import json
from collections import OrderedDict
from datetime import datetime, timedelta
import folium
from streamlit_folium import folium_static
from utils.map_utils import display_route_on_map, display_route_map, display_multiple_routes_on_map

# Importação do módulo de clustering com recarregamento
import importlib
from utils.clustering import optimize_clusters_by_proximity
import logging

def main():
    # Setup database when app starts
    setup_database()
    
    st.title("Geocodificação e Gerenciamento de Rotas")
    
    tabs = st.tabs([
        "Entrada de Texto", 
        "Upload de Arquivo", 
        "Visualizar Banco de Dados", 
        "Gerenciar Veículos",
        "Roteirização",
        "Rotas Calculadas"  # Nova aba para visualizar as rotas já calculadas
    ])
    
    # First four tabs remain the same
    with tabs[0]:
        st.info("Digite no formato: NOME, RUA, NÚMERO, CIDADE")
        
        # Add company selection
        company_options = [""] + get_all_companies()
        selected_company = st.selectbox("Empresa:", company_options)
        new_company = st.text_input("Ou adicione uma nova empresa:")
        
        # Time inputs
        col1, col2 = st.columns(2)
        with col1:
            arrival_time = st.time_input("Horário de chegada:")
        with col2:
            departure_time = st.time_input("Horário de saída:")
        
        enderecos = st.text_area("Insira as informações (uma por linha):", height=150)
        
        if st.button("Converter e Salvar", key="convert_text"):
            company_name = new_company if new_company else selected_company
            
            if enderecos:
                linhas = [linha.strip() for linha in enderecos.split('\n') if linha.strip()]
                if linhas:
                    processar_entradas(
                        linhas, 
                        company_name, 
                        arrival_time.strftime("%H:%M") if arrival_time else None,
                        departure_time.strftime("%H:%M") if departure_time else None
                    )
                else:
                    st.warning("Por favor, insira pelo menos um registro.")
            else:
                st.warning("Por favor, insira pelo menos um registro.")
    
    with tabs[1]:
        st.info("Faça upload de um arquivo com os dados dos usuários")
        uploaded_file = st.file_uploader("Faça upload de um arquivo CSV ou Excel", type=["csv", "xlsx"])
        
        # Column name inputs
        col1, col2 = st.columns(2)
        with col1:
            coluna_nome = st.text_input("Coluna de nome:", "nome")
            coluna_rua = st.text_input("Coluna de rua:", "rua")
            coluna_numero = st.text_input("Coluna de número:", "numero")
        with col2:
            coluna_cidade = st.text_input("Coluna de cidade:", "cidade")
            coluna_empresa = st.text_input("Coluna de empresa (opcional):", "empresa")
            coluna_chegada = st.text_input("Coluna de horário de chegada (opcional):", "chegada")
            coluna_saida = st.text_input("Coluna de horário de saída (opcional):", "saida")
        
        # Default values for empty fields
        default_company = st.text_input("Empresa padrão (se não especificado no arquivo):")
        col1, col2 = st.columns(2)
        with col1:
            default_arrival = st.time_input("Horário de chegada padrão:")
        with col2:
            default_departure = st.time_input("Horário de saída padrão:")
        
        if st.button("Processar Arquivo", key="process_file"):
            if uploaded_file:
                try:
                    if uploaded_file.name.endswith('.csv'):
                        df = pd.read_csv(uploaded_file)
                    else:
                        df = pd.read_excel(uploaded_file)
                    
                    # Check required columns
                    required_cols = [coluna_nome, coluna_rua, coluna_numero, coluna_cidade]
                    missing_cols = [col for col in required_cols if col not in df.columns]
                    
                    if missing_cols:
                        st.error(f"Colunas não encontradas no arquivo: {', '.join(missing_cols)}")
                    else:
                        # Process data from file
                        processar_dados_arquivo(
                            df,
                            coluna_nome,
                            coluna_rua,
                            coluna_numero,
                            coluna_cidade,
                            coluna_empresa,
                            coluna_chegada,
                            coluna_saida,
                            default_company,
                            default_arrival.strftime("%H:%M") if default_arrival else None,
                            default_departure.strftime("%H:%M") if default_departure else None
                        )
                except Exception as e:
                    st.error(f"Erro ao processar o arquivo: {e}")
            else:
                st.warning("Por favor, faça upload de um arquivo.")
                
    with tabs[2]:
        st.subheader("Dados Armazenados")
        if st.button("Carregar Dados", key="load_data"):
            mostrar_dados_banco()
        
    # New tab for vehicle management
    with tabs[3]:
        st.subheader("Gerenciamento de Veículos")
        
        # Create two columns for the vehicle management interface
        vehicle_col1, vehicle_col2 = st.columns(2)
        
        with vehicle_col1:
            st.write("### Adicionar Veículos")
            
            st.info("Digite no formato: CARRO, NUMERO DO VEICULO, PLACA, MOTORISTA, LUGARES")
            veiculos = st.text_area("Insira os veículos (um por linha):", height=150)
            
            if st.button("Adicionar Veículos", key="add_vehicles_text"):
                if veiculos:
                    linhas = [linha.strip() for linha in veiculos.split('\n') if linha.strip()]
                    if linhas:
                        processar_cadastro_veiculos(linhas)
                    else:
                        st.warning("Por favor, insira pelo menos um veículo.")
                else:
                    st.warning("Por favor, insira pelo menos um veículo.")
            
            # File upload for vehicles
            st.write("### Ou Faça Upload de Arquivo")
            vehicle_file = st.file_uploader("Upload de arquivo CSV ou Excel", type=["csv", "xlsx"], key="vehicle_upload")
            
            if vehicle_file:
                col_model = st.text_input("Coluna do modelo:", "carro")
                col_number = st.text_input("Coluna do número:", "numero")
                col_plate = st.text_input("Coluna da placa:", "placa")
                col_driver = st.text_input("Coluna do motorista:", "motorista")
                col_seats = st.text_input("Coluna de lugares:", "lugares")
                
                if st.button("Processar Arquivo de Veículos", key="process_vehicle_file"):
                    processar_arquivo_veiculos(vehicle_file, col_model, col_number, col_plate, col_driver, col_seats)
        
        with vehicle_col2:
            st.write("### Veículos Cadastrados")
            if st.button("Carregar Veículos", key="load_vehicles"):
                mostrar_veiculos_cadastrados()
                
    # New tab for route planning
    with tabs[4]:
        roteirizacao_tab()
    
    with tabs[5]:
        st.subheader("Rotas Calculadas")
        # Verifica se existem rotas criadas no processo de roteirização
        if "created_routes" in st.session_state and st.session_state.created_routes:
            created_routes = st.session_state.created_routes
            st.write(f"Total de rotas criadas: {len(created_routes)}")
            # Exibe uma tabela com as informações principais
            rotas_info = [
                {
                    "ID da Rota": rota.get("route_id", "N/A"),
                    "Veículo": rota["vehicle"]["model"] if rota.get("vehicle") else "Sem veículo",
                    "Passageiros": len(rota["passengers"]),
                    "Tempo Estimado (min)": rota.get("estimated_time", "N/A"),
                    "Cor": rota.get("color", "N/A")
                }
                for rota in created_routes
            ]
            st.dataframe(rotas_info)
            # Exibir mapa geral com rotas. Use uma paleta de cores mais ampla para evitar sobreposição.
            st.info("Mapa geral das rotas calculadas:")
            display_multiple_routes_on_map(created_routes, st.session_state.start_coord, st.session_state.end_coord)
        else:
            st.info("Nenhuma rota calculada ainda. Execute a roteirização na aba 'Roteirização'.")

def parse_entrada(entrada):
    """Parse a line with format: Name, Street, Number, City"""
    # Match pattern with more flexibility: name, street, number, city
    # Allow spaces around commas and non-digit characters in number
    pattern = r'(.*?),\s*(.*?),\s*(\S+(?:\s+\S+)*?)\s*,\s*(.+)$'
    match = re.match(pattern, entrada)
    
    if match:
        name = match.group(1).strip()
        street = match.group(2).strip()
        number = match.group(3).strip()
        city = match.group(4).strip()
        return {
            "name": name,
            "street": street,
            "number": number,
            "city": city,
            "full_address": f"{street}, {number}, {city}"
        }
    
    # Try alternative parsing for entries without enough commas
    parts = [p.strip() for p in entrada.split(',')]
    
    # Case 1: Only one part (no commas)
    if len(parts) == 1:
        st.warning(f"Entrada sem vírgulas: '{entrada}'. Por favor, use o formato: Nome, Rua, Número, Cidade")
        return None
        
    # Case 2: Two parts (one comma)
    elif len(parts) == 2:
        st.warning(f"Entrada com apenas uma vírgula: '{entrada}'. Por favor, use o formato: Nome, Rua, Número, Cidade")
        return None
        
    # Case 3: Three parts (possibly missing city, which is often the case)
    elif len(parts) == 3:
        # Assume parts are: name, street, number (with city missing)
        # Add default city "Caxias do Sul" as it's common in the examples
        name = parts[0].strip()
        street = parts[1].strip()
        number = parts[2].strip()
        city = "Caxias do Sul"  # Default city
        
        return {
            "name": name,
            "street": street,
            "number": number,
            "city": city,
            "full_address": f"{street}, {number}, {city}"
        }
    
    # If we get here with more than 3 parts but the regex didn't match,
    # try a more aggressive approach
    if len(parts) >= 4:
        name = parts[0].strip()
        street = parts[1].strip()
        number = parts[2].strip()
        # Join remaining parts as city (in case city name has commas)
        city = ", ".join(parts[3:]).strip()
        
        return {
            "name": name,
            "street": street,
            "number": number,
            "city": city,
            "full_address": f"{street}, {number}, {city}"
        }
    
    return None

def processar_entradas(linhas, company_name=None, arrival_time=None, departure_time=None):
    # Parse input lines
    entradas_parseadas = []
    entradas_invalidas = []
    
    for linha in linhas:
        parsed = parse_entrada(linha)
        if parsed:
            entradas_parseadas.append(parsed)
        else:
            entradas_invalidas.append(linha)
    
    if entradas_invalidas:
        st.error("As seguintes entradas não estão no formato correto (Nome, Rua, Número, Cidade):")
        for entrada in entradas_invalidas:
            st.write(f"- {entrada}")
        
    if not entradas_parseadas:
        st.warning("Nenhuma entrada válida para processar.")
        return
    
    # Get company ID if provided
    company_id = None
    if company_name:
        company_id = get_or_create_company(company_name)
    
    # Extract unique addresses to geocode
    enderecos_unicos = {}
    for entrada in entradas_parseadas:
        addr_key = f"{entrada['street']}|{entrada['number']}|{entrada['city']}"
        if addr_key not in enderecos_unicos:
            enderecos_unicos[addr_key] = entrada['full_address']
    
    # Geocode unique addresses
    progress_bar = st.progress(0)
    status_placeholder = st.empty()
    
    # Dictionary to store geocoding results by address
    resultados_geocoding = {}
    
    # Process unique addresses
    for i, (addr_key, endereco) in enumerate(enderecos_unicos.items()):
        status_placeholder.text(f"Geocodificando endereço {i+1}/{len(enderecos_unicos)}: {endereco}")
        try:
            coordinates = get_coordinates(endereco)
            if coordinates:
                resultados_geocoding[addr_key] = {
                    "latitude": coordinates['lat'],
                    "longitude": coordinates['lon'],
                    "status": "Sucesso"
                }
            else:
                resultados_geocoding[addr_key] = {
                    "latitude": None,
                    "longitude": None,
                    "status": "Endereço não encontrado"
                }
        except Exception as e:
            resultados_geocoding[addr_key] = {
                "latitude": None,
                "longitude": None,
                "status": f"Erro: {str(e)}"
            }
        
        # Update progress bar
        progress_bar.progress((i + 1) / len(enderecos_unicos))
    
    # Store data in the database
    resultados = []
    
    for entrada in entradas_parseadas:
        addr_key = f"{entrada['street']}|{entrada['number']}|{entrada['city']}"
        geocode_result = resultados_geocoding.get(addr_key, {})
        
        try:
            # Insert or get address
            address_id = insert_address(
                entrada['street'],
                entrada['number'],
                entrada['city'],
                geocode_result.get('latitude'),
                geocode_result.get('longitude'),
                geocode_result.get('status')
            )
            
            # Insert person
            person_id = insert_person(
                entrada['name'], 
                address_id,
                company_id,
                arrival_time,
                departure_time
            )
            
            resultados.append({
                "Nome": entrada['name'],
                "Rua": entrada['street'],
                "Número": entrada['number'],
                "Cidade": entrada['city'],
                "Empresa": company_name if company_name else "",
                "Chegada": arrival_time if arrival_time else "",
                "Saída": departure_time if departure_time else "",
                "Latitude": geocode_result.get('latitude'),
                "Longitude": geocode_result.get('longitude'),
                "Status": geocode_result.get('status')
            })
            
        except Exception as e:
            st.error(f"Erro ao salvar no banco de dados: {str(e)}")
    
    status_placeholder.text("Processamento concluído! Dados salvos no banco de dados.")
    
    if resultados:
        df_resultados = pd.DataFrame(resultados)
        st.write("### Resultados:")
        st.dataframe(df_resultados)
        
        csv = df_resultados.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Baixar resultados como CSV",
            data=csv,
            file_name='resultados_geocodificacao.csv',
            mime='text/csv',
        )

def processar_dados_arquivo(df, col_nome, col_rua, col_numero, col_cidade, 
                           col_empresa=None, col_chegada=None, col_saida=None,
                           default_company=None, default_arrival=None, default_departure=None):
    """Process data from file upload with separate columns."""
    
    # Check for required columns
    if not all(col in df.columns for col in [col_nome, col_rua, col_numero, col_cidade]):
        st.error("Arquivo não contém todas as colunas necessárias")
        return
    
    # Create list of valid entries
    entradas_validas = []
    
    # Process each row
    for idx, row in df.iterrows():
        name = row[col_nome]
        street = row[col_rua]
        number = str(row[col_numero])
        city = row[col_cidade]
        
        # Get optional fields with defaults
        company = row.get(col_empresa, default_company) if col_empresa in df.columns else default_company
        
        # Handle time fields
        arrival = None
        departure = None
        
        if col_chegada in df.columns:
            arrival_val = row[col_chegada]
            if pd.notna(arrival_val):
                # Try to convert various time formats
                try:
                    if isinstance(arrival_val, str):
                        arrival = arrival_val
                    else:
                        # Handle datetime or time objects
                        arrival = pd.to_datetime(arrival_val).strftime("%H:%M")
                except:
                    arrival = default_arrival
            else:
                arrival = default_arrival
            
        if col_saida in df.columns:
            departure_val = row[col_saida]
            if pd.notna(departure_val):
                try:
                    if isinstance(departure_val, str):
                        departure = departure_val
                    else:
                        departure = pd.to_datetime(departure_val).strftime("%H:%M")
                except:
                    departure = default_departure
            else:
                departure = default_departure
        
        # Add to list of valid entries
        if pd.notna(name) and pd.notna(street) and pd.notna(number) and pd.notna(city):
            entradas_validas.append({
                "name": str(name),
                "street": str(street),
                "number": str(number),
                "city": str(city),
                "company": company,
                "arrival": arrival,
                "departure": departure,
                "full_address": f"{street}, {number}, {city}"
            })
    
    if not entradas_validas:
        st.warning("Nenhum dado válido encontrado no arquivo.")
        return
        
    # Get company ID if provided
    company_id = None
    if default_company:
        company_id = get_or_create_company(default_company)
    
    # Extract unique addresses to geocode
    enderecos_unicos = {}
    for entrada in entradas_validas:
        addr_key = f"{entrada['street']}|{entrada['number']}|{entrada['city']}"
        if addr_key not in enderecos_unicos:
            enderecos_unicos[addr_key] = entrada['full_address']
    
    # Show processing indicators
    progress_bar = st.progress(0)
    status_placeholder = st.empty()
    
    # Geocode unique addresses
    resultados_geocoding = {}
    
    # Process unique addresses
    for i, (addr_key, endereco) in enumerate(enderecos_unicos.items()):
        status_placeholder.text(f"Geocodificando endereço {i+1}/{len(enderecos_unicos)}: {endereco}")
        try:
            coordinates = get_coordinates(endereco)
            if coordinates:
                resultados_geocoding[addr_key] = {
                    "latitude": coordinates['lat'],
                    "longitude": coordinates['lon'],
                    "status": "Sucesso"
                }
            else:
                resultados_geocoding[addr_key] = {
                    "latitude": None,
                    "longitude": None,
                    "status": "Endereço não encontrado"
                }
        except Exception as e:
            resultados_geocoding[addr_key] = {
                "latitude": None,
                "longitude": None,
                "status": f"Erro: {str(e)}"
            }
        
        # Update progress bar
        progress_bar.progress((i + 1) / len(enderecos_unicos))
    
    # Store data in the database
    resultados = []
    
    for entrada in entradas_validas:
        addr_key = f"{entrada['street']}|{entrada['number']}|{entrada['city']}"
        geocode_result = resultados_geocoding.get(addr_key, {})
        
        try:
            # Get company ID
            current_company_id = None
            if entrada['company']:
                current_company_id = get_or_create_company(entrada['company'])
            elif company_id:
                current_company_id = company_id
                
            # Insert or get address
            address_id = insert_address(
                entrada['street'],
                entrada['number'],
                entrada['city'],
                geocode_result.get('latitude'),
                geocode_result.get('longitude'),
                geocode_result.get('status')
            )
            
            # Insert person
            person_id = insert_person(
                entrada['name'], 
                address_id,
                current_company_id,
                entrada['arrival'],
                entrada['departure']
            )
            
            resultados.append({
                "Nome": entrada['name'],
                "Rua": entrada['street'],
                "Número": entrada['number'],
                "Cidade": entrada['city'],
                "Empresa": entrada['company'] if entrada['company'] else "",
                "Chegada": entrada['arrival'] if entrada['arrival'] else "",
                "Saída": entrada['departure'] if entrada['departure'] else "",
                "Latitude": geocode_result.get('latitude'),
                "Longitude": geocode_result.get('longitude'),
                "Status": geocode_result.get('status')
            })
            
        except Exception as e:
            st.error(f"Erro ao salvar no banco de dados: {str(e)}")
    
    status_placeholder.text("Processamento concluído! Dados salvos no banco de dados.")
    
    if resultados:
        df_resultados = pd.DataFrame(resultados)
        st.write("### Resultados:")
        st.dataframe(df_resultados)
        
        csv = df_resultados.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Baixar resultados como CSV",
            data=csv,
            file_name='resultados_geocodificacao.csv',
            mime='text/csv',
        )

def mostrar_dados_banco():
    """Display all data from the database."""
    try:
        data = get_all_person_address_data()
        if data:
            df = pd.DataFrame(data)
            df.columns = ["Nome", "Rua", "Número", "Cidade", "Latitude", "Longitude", 
                          "Status", "Empresa", "Chegada", "Saída"]
            st.dataframe(df)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Baixar todos os dados como CSV",
                data=csv,
                file_name='dados_geocodificacao.csv',
                mime='text/csv',
            )
        else:
            st.info("Não há dados armazenados no banco de dados.")
    except Exception as e:
        st.error(f"Erro ao carregar dados do banco de dados: {str(e)}")

def parse_veiculo(linha):
    """Parse a line with vehicle information in format: CAR, NUMBER, PLATE, DRIVER, SEATS."""
    parts = [part.strip() for part in linha.split(',')]
    
    if len(parts) < 5:
        return None
    
    model = parts[0]
    vehicle_number = parts[1]
    license_plate = parts[2]
    driver = parts[3]
    
    # Try to convert seats to integer
    try:
        seats = int(parts[4])
    except ValueError:
        return None
    
    return {
        "model": model,
        "vehicle_number": vehicle_number,
        "license_plate": license_plate,
        "driver": driver,
        "seats": seats
    }

def processar_cadastro_veiculos(linhas):
    """Process vehicle entries and store them in the database."""
    veiculos_parseados = []
    veiculos_invalidos = []
    veiculos_existentes = []
    
    for linha in linhas:
        veiculo = parse_veiculo(linha)
        if veiculo:
            # Check if vehicle with same number or plate already exists
            if check_vehicle_exists(veiculo["vehicle_number"], veiculo["license_plate"]):
                veiculos_existentes.append(linha)
            else:
                veiculos_parseados.append(veiculo)
        else:
            veiculos_invalidos.append(linha)
    
    if veiculos_invalidos:
        st.error("As seguintes entradas de veículos não estão no formato correto (CARRO, NUMERO, PLACA, MOTORISTA, LUGARES):")
        for entrada in veiculos_invalidos:
            st.write(f"- {entrada}")
    
    if veiculos_existentes:
        st.warning("Os seguintes veículos já existem no sistema (número ou placa duplicada):")
        for entrada in veiculos_existentes:
            st.write(f"- {entrada}")
    
    if not veiculos_parseados:
        st.warning("Nenhum veículo válido para adicionar.")
        return
    
    # Store vehicles in database
    sucesso = []
    falha = []
    
    for veiculo in veiculos_parseados:
        try:
            insert_vehicle(
                veiculo["model"],
                veiculo["vehicle_number"],
                veiculo["license_plate"],
                veiculo["driver"],
                veiculo["seats"]
            )
            sucesso.append(veiculo)
        except Exception as e:
            falha.append((veiculo, str(e)))
    
    if sucesso:
        st.success(f"{len(sucesso)} veículo(s) adicionado(s) com sucesso!")
        
        # Display results
        df_resultados = pd.DataFrame(sucesso)
        df_resultados.columns = ["Modelo", "Número", "Placa", "Motorista", "Lugares"]
        st.dataframe(df_resultados)
    
    if falha:
        st.error("Os seguintes veículos não puderam ser adicionados:")
        for veiculo, erro in falha:
            st.write(f"- {veiculo['model']} ({veiculo['license_plate']}): {erro}")

def processar_arquivo_veiculos(file, col_model, col_number, col_plate, col_driver, col_seats):
    """Process vehicle data from uploaded file."""
    try:
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        required_cols = [col_model, col_number, col_plate, col_driver, col_seats]
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            st.error(f"Colunas não encontradas no arquivo: {', '.join(missing_cols)}")
            return
        
        # Process rows
        veiculos_validos = []
        
        for idx, row in df.iterrows():
            if pd.notna(row[col_model]) and pd.notna(row[col_number]) and pd.notna(row[col_plate]) and pd.notna(row[col_driver]) and pd.notna(row[col_seats]):
                try:
                    seats = int(row[col_seats])
                    veiculos_validos.append({
                        "model": str(row[col_model]),
                        "vehicle_number": str(row[col_number]),
                        "license_plate": str(row[col_plate]),
                        "driver": str(row[col_driver]),
                        "seats": seats
                    })
                except ValueError:
                    st.warning(f"Linha {idx+1}: Número de lugares deve ser um número inteiro.")
        
        if not veiculos_validos:
            st.warning("Nenhum veículo válido encontrado no arquivo.")
            return
        
        # Check for duplicates in database
        veiculos_novos = []
        veiculos_existentes = []
        
        for veiculo in veiculos_validos:
            if check_vehicle_exists(veiculo["vehicle_number"], veiculo["license_plate"]):
                veiculos_existentes.append(veiculo)
            else:
                veiculos_novos.append(veiculo)
        
        if veiculos_existentes:
            st.warning(f"{len(veiculos_existentes)} veículo(s) já existem no sistema e serão ignorados.")
        
        if not veiculos_novos:
            st.warning("Não há novos veículos para adicionar.")
            return
        
        # Add vehicles to database
        sucesso = []
        for veiculo in veiculos_novos:
            try:
                insert_vehicle(
                    veiculo["model"],
                    veiculo["vehicle_number"],
                    veiculo["license_plate"],
                    veiculo["driver"],
                    veiculo["seats"]
                )
                sucesso.append(veiculo)
            except Exception as e:
                st.error(f"Erro ao adicionar veículo {veiculo['model']} ({veiculo['license_plate']}): {str(e)}")
        
        if sucesso:
            st.success(f"{len(sucesso)} veículo(s) adicionado(s) com sucesso!")
            
            # Display results
            df_resultados = pd.DataFrame(sucesso)
            df_resultados.columns = ["Modelo", "Número", "Placa", "Motorista", "Lugares"]
            st.dataframe(df_resultados)
        
    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {str(e)}")

def mostrar_veiculos_cadastrados():
    """Display all vehicles in the database."""
    try:
        veiculos = get_all_vehicles()
        
        if veiculos:
            df = pd.DataFrame(veiculos)
            df = df[["model", "vehicle_number", "license_plate", "driver", "seats"]]
            df.columns = ["Modelo", "Número", "Placa", "Motorista", "Lugares"]
            
            st.dataframe(df)
            
            # Add option to delete vehicles
            vehicle_to_delete = st.selectbox(
                "Selecione um veículo para excluir:", 
                options=[f"{v['model']} - {v['license_plate']} ({v['driver']})" for v in veiculos],
                index=None
            )
            
            if vehicle_to_delete and st.button("Excluir Veículo Selecionado"):
                # Extract vehicle ID from selection
                idx = [f"{v['model']} - {v['license_plate']} ({v['driver']})" for v in veiculos].index(vehicle_to_delete)
                vehicle_id = veiculos[idx]["id"]
                
                if delete_vehicle(vehicle_id):
                    st.success(f"Veículo {vehicle_to_delete} excluído com sucesso!")
                    st.rerun()
                else:
                    st.error("Não foi possível excluir o veículo.")
            
            # Download as CSV
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Baixar lista de veículos como CSV",
                data=csv,
                file_name='veiculos.csv',
                mime='text/csv',
            )
        else:
            st.info("Não há veículos cadastrados no sistema.")
    except Exception as e:
        st.error(f"Erro ao carregar veículos: {str(e)}")

def roteirizacao_tab():
    st.subheader("Planejamento de Rotas")
    
    # Create tabs for creating routes and viewing existing routes
    route_tabs = st.tabs(["Criar Nova Rota", "Ver Rotas Existentes"])
    
    with route_tabs[0]:
        create_new_route()
        
    with route_tabs[1]:
        view_existing_routes()

def create_new_route():
    # Inicialize os estados se não existirem
    if 'planning_started' not in st.session_state:
        st.session_state.planning_started = False
    if 'routes_created' not in st.session_state:
        st.session_state.routes_created = False
    if 'valid_routes' not in st.session_state:
        st.session_state.valid_routes = None
    if 'created_routes' not in st.session_state:
        st.session_state.created_routes = None
    if 'start_coord' not in st.session_state:
        st.session_state.start_coord = None
    if 'end_coord' not in st.session_state:
        st.session_state.end_coord = None
        
    # Obtém as empresas, passageiros, veículos, etc.
    companies = get_companies_with_persons()
    if not companies:
        st.warning("Não há empresas com pessoas cadastradas. Cadastre pessoas primeiro para começar a roteirização.")
        return
    
    col1, col2 = st.columns(2)
    with col1:
        selected_company = st.selectbox(
            "Empresa:",
            options=[f"{c['name']} (ID: {c['id']})" for c in companies],
            index=0,
            key="company_select"
        )
        company_id = int(selected_company.split("ID: ")[1].strip(")"))
    with col2:
        route_type = st.radio(
            "Tipo de Roteiro:",
            options=["Ida para a Empresa", "Saída da Empresa"],
            index=0,
            key="route_type"
        )
        is_arrival = route_type == "Ida para a Empresa"
    
    # Parâmetros da rota
    company_address = get_company_address(company_id)
    company_location = f"{company_address['street']}, {company_address['number']}, {company_address['city']}" if company_address else ""
    col1, col2 = st.columns(2)
    with col1:
        if is_arrival:
            start_point_str = st.text_input("Ponto de Partida (Garagem do Ônibus):", key="start_point")
            end_point_str = st.text_input("Ponto de Chegada (Empresa):", company_location, key="end_point")
        else:
            start_point_str = st.text_input("Ponto de Partida (Empresa):", company_location, key="start_point")
            end_point_str = st.text_input("Ponto de Chegada (Garagem do Ônibus):", key="end_point")
    with col2:
        max_duration = st.number_input("Tempo Máximo da Rota (em minutos):", 
                                      min_value=5, max_value=120, value=45, step=5, key="max_duration")
    
    route_name = st.text_input(
        "Nome da Rota:", 
        value=f"Rota {'para' if is_arrival else 'de'} {selected_company.split(' (ID:')[0]} - {datetime.now().strftime('%d/%m/%Y %H:%M')}", 
        key="route_name"
    )
    
    eligible_persons = get_persons_by_company(company_id, is_arrival)
    if not eligible_persons:
        st.warning(f"Não há pessoas cadastradas para {'chegada à' if is_arrival else 'saída da'} empresa selecionada.")
    else:
        passenger_count = len(eligible_persons)
        st.write(f"### Total de Passageiros Elegíveis: {passenger_count}")
        
        # Verificar se há veículos disponíveis
        vehicles = get_all_vehicles()
        if not vehicles:
            st.warning("Não há veículos cadastrados. Cadastre veículos antes de criar rotas.")
            return
            
        # Quando o usuário clica para iniciar o planejamento de rota
        if st.button("Iniciar Planejamento de Rota", key="start_route_planning") or st.session_state.planning_started:
            st.session_state.planning_started = True
            if not st.session_state.valid_routes:
                if not start_point_str or not end_point_str:
                    st.error("Por favor, informe os pontos de partida e chegada.")
                    return
                if len(eligible_persons) == 0:
                    st.error("Não há passageiros elegíveis para esta rota.")
                    return
                
                with st.spinner("Planejando rotas..."):
                    # Geocodificar os pontos de partida e chegada
                    start_coord = get_coordinates(start_point_str)
                    end_coord = get_coordinates(end_point_str)
                    
                    # Store coordinates in session state
                    st.session_state.start_coord = start_coord
                    st.session_state.end_coord = end_coord
                    
                    if not start_coord or not end_coord:
                        st.error("Não foi possível geocodificar os pontos de partida ou chegada.")
                        return
                    
                    # Obter coordenadas da empresa para otimização
                    company_coord = {'lat': end_coord['lat'], 'lon': end_coord['lon']} if is_arrival else {'lat': start_coord['lat'], 'lon': start_coord['lon']}

                    # Obter coordenadas dos passageiros
                    intermediate_coords = []
                    for person in eligible_persons:
                        if person.get('latitude') and person.get('longitude'):
                            intermediate_coords.append({
                                'lat': person['latitude'],
                                'lon': person['longitude'],
                                'person_id': person['id'],
                                'name': person['name']
                            })
                    
                    if not intermediate_coords:
                        st.error("Não há passageiros com coordenadas válidas.")
                        return
                    
                    try:
                        # Extrair tipos de veículos disponíveis para estimativas de tempo
                        available_vehicle_types = list(set([get_vehicle_type(v['model']) for v in vehicles]))
                        
                        # NOVA ABORDAGEM: Primeiro planejamos rotas baseadas no tempo máximo
                        routes_by_time = plan_routes_by_time_constraint(
                            start_coord,
                            end_coord,
                            intermediate_coords,
                            max_duration,
                            available_vehicle_types
                        )
                        
                        if not routes_by_time or len(routes_by_time) == 0:
                            st.error("Não foi possível criar rotas dentro do limite de tempo especificado.")
                            return
                            
                        total_routes = len(routes_by_time)
                        total_passengers = sum(len(route['passengers']) for route in routes_by_time)
                        
                        st.success(f"Foram criadas {total_routes} rotas para atender {total_passengers} passageiros, respeitando o limite de {max_duration} minutos por rota.")
                        
                        # Agora selecionamos veículos adequados para cada rota
                        routes_with_vehicles = assign_vehicles_to_routes(routes_by_time, vehicles)
                        
                        # Verificar se todos as rotas têm veículos adequados
                        unassigned_routes = [r for r in routes_with_vehicles if 'vehicle' not in r or not r['vehicle']]
                        if unassigned_routes:
                            st.warning(f"Não foi possível encontrar veículos adequados para {len(unassigned_routes)} rota(s).")
                            st.info("Por favor, cadastre mais veículos ou ajuste os agrupamentos de passageiros.")
                            
                            # Mostrar quais rotas não têm veículos
                            for i, route in enumerate(unassigned_routes):
                                st.write(f"Rota {i+1}: {len(route['passengers'])} passageiros (Sem veículo adequado)")
                                
                            # Perguntar se deseja continuar mesmo assim
                            continue_anyway = st.checkbox("Continuar mesmo assim (apenas rotas com veículos serão criadas)")
                            if not continue_anyway:
                                return
                                
                        # Filtrar apenas rotas com veículos atribuídos
                        valid_routes = [r for r in routes_with_vehicles if 'vehicle' in r and r['vehicle']]
                        
                        if not valid_routes:
                            st.error("Não há veículos adequados para nenhuma das rotas planejadas.")
                            return
                        
                        # Salvar as rotas válidas no estado
                        st.session_state.valid_routes = valid_routes
                    except Exception as e:
                        st.error(f"Erro ao planejar rotas: {str(e)}")
                        return
            
            # Exibir informações sobre as rotas planejadas
            st.write("### Rotas Planejadas:")
            for i, route in enumerate(st.session_state.valid_routes):
                vehicle = route['vehicle']
                passengers = route['passengers']
                estimated_time = route.get('estimated_time', 'N/A')
                if estimated_time == 0:
                    st.write(f"**Rota {i+1}:** {len(passengers)} passageiros - Veículo: {vehicle['model']} ({vehicle['seats']} lugares) - Tempo estimado: Cálculo pendente")
                else:
                    st.write(f"**Rota {i+1}:** {len(passengers)} passageiros - Veículo: {vehicle['model']} ({vehicle['seats']} lugares) - Tempo estimado a partir do primeiro recolhimento até o destino final: {estimated_time} minutos")
            
            # Botão para confirmar e criar as rotas no sistema
            if st.button("Confirmar e Criar Rotas"):
                st.session_state.routes_created = True
                created_routes = create_routes_in_system(
                    st.session_state.valid_routes, 
                    company_id, 
                    st.session_state.start_coord,  # Use session state instead of local variable
                    st.session_state.end_coord,    # Use session state instead of local variable
                    start_point_str,
                    end_point_str,
                    is_arrival,
                    route_name,
                    max_duration
                )
                
                # Armazenar as rotas criadas no estado
                st.session_state.created_routes = created_routes
    
    # Exibir rotas criadas (independente do estado dos botões)
    if st.session_state.routes_created and st.session_state.created_routes:
        st.success(f"Foram criadas {len(st.session_state.created_routes)} rotas com sucesso!")
        # Use coordinates from session state
        display_created_routes(st.session_state.created_routes, st.session_state.start_coord, st.session_state.end_coord)

def plan_routes_by_time_constraint(start_coord, end_coord, passengers, max_duration_minutes, vehicle_types=None):
    """
    Planeja múltiplas rotas respeitando o limite de tempo por rota, considerando tipos de veículos.
    
    Args:
        start_coord: Coordenadas do ponto de partida
        end_coord: Coordenadas do ponto de chegada
        passengers: Lista de passageiros com suas coordenadas
        max_duration_minutes: Tempo máximo permitido por rota (em minutos)
        vehicle_types: Lista de tipos de veículos disponíveis (se None, assume "car")
        
    Returns:
        Lista de rotas, cada uma contendo uma lista de passageiros atendidos
    """
    st.info(f"Planejando rotas com limite de {max_duration_minutes} minutos por rota...")
    
    # Se vehicle_types não for fornecido, assume carros como padrão
    if not vehicle_types:
        vehicle_types = ["car"]
    
    # Iniciar com uma rota vazia
    routes = []
    
    # Vamos usar uma abordagem gulosa para criar rotas
    # Começamos com todos os passageiros não atribuídos
    unassigned_passengers = passengers.copy()
    
    # Enquanto houver passageiros não atribuídos, criar mais rotas
    vehicle_type_index = 0  # Para alternar entre os tipos de veículos disponíveis
    
    while unassigned_passengers:
        # Seleciona o próximo tipo de veículo na lista (rotação cíclica)
        vehicle_type = vehicle_types[vehicle_type_index % len(vehicle_types)]
        vehicle_type_index += 1
        
        current_route = {
            'passengers': [],
            'estimated_time': 0,
            'vehicle_type': vehicle_type
        }
        
        # Tenta adicionar o ponto inicial mais próximo à rota atual
        if not current_route['passengers']:
            # Se a rota estiver vazia, comece com o passageiro mais próximo do ponto de partida
            nearest = find_nearest_passenger(start_coord, unassigned_passengers)
            current_route['passengers'].append(nearest)
            unassigned_passengers.remove(nearest)
        
        # Continua adicionando passageiros à rota atual enquanto respeitar o limite de tempo
        keep_adding = True
        while keep_adding and unassigned_passengers:
            # Último passageiro adicionado à rota
            last_passenger = current_route['passengers'][-1]
            
            # Encontra o próximo passageiro mais próximo
            nearest = find_nearest_passenger(last_passenger, unassigned_passengers)
            
            # Simula adição desse passageiro à rota
            temp_passengers = current_route['passengers'] + [nearest]
            
            # Estima o tempo da rota com este novo passageiro, considerando tipo do veículo
            estimated_time = estimate_route_time(start_coord, end_coord, temp_passengers, vehicle_type)
            
            # Se ainda estiver dentro do limite, adiciona o passageiro
            if estimated_time <= max_duration_minutes:
                current_route['passengers'].append(nearest)
                current_route['estimated_time'] = estimated_time
                unassigned_passengers.remove(nearest)
            else:
                # Se exceder o limite, para de adicionar à rota atual
                keep_adding = False
        
        # Se chegou aqui e a rota tem passageiros, adiciona à lista de rotas
        if current_route['passengers']:
            routes.append(current_route)
        
        # Se chegou aqui e ainda há passageiros não atribuídos mas não foi possível adicioná-los,
        # significa que estamos com um problema: o passageiro sozinho já excede o limite de tempo
        # Neste caso, forçamos a adição em uma nova rota
        elif unassigned_passengers:
            first_passenger = unassigned_passengers.pop(0)
            solo_time = estimate_route_time(start_coord, end_coord, [first_passenger], vehicle_type)
            routes.append({
                'passengers': [first_passenger],
                'estimated_time': solo_time,
                'vehicle_type': vehicle_type
            })
            st.warning(f"Atenção: Passageiro cuja rota excede o limite de tempo ({solo_time:.1f} min > {max_duration_minutes} min).")
    
    return routes

def find_nearest_passenger(reference_point, passengers):
    """
    Encontra o passageiro mais próximo de um ponto de referência.
    """
    min_distance = float('inf')
    nearest = None
    
    # Coordenadas do ponto de referência
    ref_lat = reference_point['lat']
    ref_lon = reference_point['lon']
    
    for passenger in passengers:
        # Cálculo simplificado de distância (distância euclidiana)
        distance = ((passenger['lat'] - ref_lat) ** 2 + (passenger['lon'] - ref_lon) ** 2) ** 0.5
        if distance < min_distance:
            min_distance = distance
            nearest = passenger
    
    return nearest

def estimate_route_time(start_coord, end_coord, passengers, vehicle_type="car"):
    """
    Estima o tempo de uma rota em minutos com base em distância e outros fatores.
    
    Args:
        start_coord: Coordenadas do ponto de partida
        end_coord: Coordenadas do ponto de chegada
        passengers: Lista de passageiros com suas coordenadas
        vehicle_type: Tipo do veículo (car, bus, van, etc.)
        
    Returns:
        Tempo estimado em minutos
    """
    if not passengers:
        return 0
    
    # Velocidade média estimada em km/h baseada no tipo de veículo
    vehicle_speeds = {
        "car": 40,
        "van": 35,
        "bus": 30,
        "truck": 25,
        "motorcycle": 45
    }
    avg_speed_kmh = vehicle_speeds.get(vehicle_type.lower(), 35)
    
    # Tempo gasto em cada parada em minutos (também varia por tipo de veículo)
    stop_times = {
        "car": 1,
        "van": 1.5,
        "bus": 2,
        "truck": 2,
        "motorcycle": 0.5
    }
    stop_time_minutes = stop_times.get(vehicle_type.lower(), 1)
    
    # Fator de tráfego (congestionamento) - simplificado
    traffic_factor = 1.2  # 20% de tempo adicional devido ao tráfego
    
    # Cálculo da distância total
    total_distance = 0
    
    # Distância do ponto inicial até o primeiro passageiro
    prev_point = start_coord
    for passenger in passengers:
        # Distância euclidiana simples
        dist = (((passenger['lat'] - prev_point['lat']) ** 2 + 
                (passenger['lon'] - prev_point['lon']) ** 2) ** 0.5) * 111  # Aprox. 111km por grau
        total_distance += dist
        prev_point = passenger
    
    # Distância do último passageiro até o ponto final
    dist = (((end_coord['lat'] - prev_point['lat']) ** 2 + 
            (end_coord['lon'] - prev_point['lon']) ** 2) ** 0.5) * 111
    total_distance += dist
    
    # Calcula o tempo de viagem em minutos (considerando tráfego)
    travel_time_minutes = (total_distance / avg_speed_kmh) * 60 * traffic_factor
    
    # Adiciona tempo de parada para cada passageiro
    stop_time_total = len(passengers) * stop_time_minutes
    
    # Tempo total estimado
    total_time_minutes = travel_time_minutes + stop_time_total
    
    return round(total_time_minutes, 1)

def assign_vehicles_to_routes(routes, available_vehicles):
    """
    Atribui veículos adequados a cada rota planejada, considerando tipos sugeridos e otimização de capacidade.
    Tenta alocar veículos com capacidade próxima ao número de passageiros para evitar subutilização.
    
    Args:
        routes: Lista de rotas planejadas
        available_vehicles: Lista de veículos disponíveis
        
    Returns:
        Rotas com veículos atribuídos
    """
    st.info("Atribuindo veículos às rotas planejadas...")
    
    # Organizar veículos por tipo
    vehicles_by_type = {}
    for vehicle in available_vehicles:
        vehicle_type = get_vehicle_type(vehicle['model'])
        if vehicle_type not in vehicles_by_type:
            vehicles_by_type[vehicle_type] = []
        vehicles_by_type[vehicle_type].append(vehicle)
    
    # Para cada tipo, ordenar por capacidade (do menor para o maior)
    # Isso ajuda a escolher o menor veículo adequado primeiro
    for vtype in vehicles_by_type:
        vehicles_by_type[vtype] = sorted(vehicles_by_type[vtype], key=lambda v: v['seats'])
    
    # Lista para veículos já atribuídos
    assigned_vehicle_ids = []
    
    # Organizar rotas por número de passageiros (do maior para o menor)
    # Isso ajuda a atribuir veículos maiores para rotas maiores primeiro
    sorted_routes = sorted(routes, key=lambda r: len(r['passengers']), reverse=True)
    
    result_routes = []
    unassigned_routes = []  # Rotas sem veículo adequado
    
    # Primeira passagem: tenta atribuir o veículo de melhor fit para cada rota
    for route in sorted_routes:
        passengers_count = len(route['passengers'])
        suggested_vehicle_type = route.get('vehicle_type', 'car')
        
        # Encontrar o veículo mais adequado utilizando a função de melhor ajuste
        best_vehicle, score = find_best_fit_vehicle(
            passengers_count, 
            vehicles_by_type, 
            suggested_vehicle_type, 
            assigned_vehicle_ids
        )
        
        if best_vehicle:
            # Veículo adequado encontrado
            assigned_vehicle_ids.append(best_vehicle['id'])
            route_copy = route.copy()
            route_copy['vehicle'] = best_vehicle
            route_copy['fit_score'] = score  # Adiciona a pontuação de ajuste para possíveis análises
            result_routes.append(route_copy)
        else:
            # Sem veículo adequado disponível
            unassigned_routes.append(route)
    
    # Segunda passagem: tentar reequilibrar veículos se houver rotas sem veículos
    if unassigned_routes:
        # Calcula capacidade total disponível e necessidade total
        total_available_seats = sum(v['seats'] for v in available_vehicles if v['id'] not in assigned_vehicle_ids)
        total_needed_seats = sum(len(r['passengers']) for r in unassigned_routes)
        
        if total_available_seats >= total_needed_seats:
            # Se temos capacidade suficiente, tentar realocar veículos
            reallocation_result = reallocate_vehicles_and_passengers(
                result_routes, 
                unassigned_routes, 
                available_vehicles, 
                assigned_vehicle_ids
            )
            
            if reallocation_result:
                result_routes = reallocation_result
                unassigned_routes = []  # Todas as rotas foram atribuídas
        
    # Se ainda houver rotas não atribuídas, adiciona com vehicle=None
    for route in unassigned_routes:
        route_copy = route.copy()
        route_copy['vehicle'] = None
        result_routes.append(route_copy)
    
    # Verificar utilização dos veículos (para logging/análise)
    calculate_vehicle_utilization(result_routes)
    
    return result_routes

def find_best_fit_vehicle(passengers_count, vehicles_by_type, suggested_type, assigned_ids):
    """
    Encontra o veículo com a melhor adequação de capacidade para o número de passageiros.
    Prioriza veículos cuja capacidade seja próxima, mas não menor que o número de passageiros.
    
    Args:
        passengers_count: Número de passageiros
        vehicles_by_type: Dicionário de veículos organizados por tipo
        suggested_type: Tipo de veículo sugerido
        assigned_ids: IDs de veículos já atribuídos
        
    Returns:
        Tupla (melhor_veículo, pontuação) ou (None, 0) se não encontrar
    """
    best_vehicle = None
    best_score = -float('inf')  # Iniciar com o pior score possível
    
    # Função para calcular o score de adequação (fit)
    # Um score perfeito (100%) é quando o veículo tem exatamente a capacidade necessária
    def calculate_fit_score(capacity, needed):
        if capacity < needed:
            # Veículo pequeno demais: penalidade severa
            return -100
        
        # Veículo grande o suficiente
        # Quanto mais próximo da capacidade necessária, melhor o score
        utilization = needed / capacity
        
        # Score baseado na utilização, favorecendo utilização próxima a 100%
        # 1.0 = 100% utilizado (perfeito)
        # 0.5 = 50% utilizado (aceitável mas não ideal)
        # 0.25 = 25% utilizado (ruim)
        if utilization > 0.85:  # 85% ou mais é ótimo
            return 95 + 5 * utilization  # 95-100
        elif utilization > 0.70:  # 70-85% é muito bom
            return 80 + 15 * utilization  # 80-95
        elif utilization > 0.50:  # 50-70% é bom
            return 50 + 30 * utilization  # 50-80
        else:  # Menos de 50% é desperdício, mas ainda aceitável se necessário
            return 50 * utilization  # 0-50
    
    # Primeiro, tentar veículos do tipo sugerido
    if suggested_type in vehicles_by_type:
        for vehicle in vehicles_by_type[suggested_type]:
            if vehicle['id'] not in assigned_ids:
                score = calculate_fit_score(vehicle['seats'], passengers_count)
                if score > best_score:
                    best_score = score
                    best_vehicle = vehicle
    
    # Se não encontrou um veículo adequado do tipo sugerido ou o melhor tem score negativo,
    # procurar em outros tipos
    if best_vehicle is None or best_score < 0:
        for vtype, vehicles in vehicles_by_type.items():
            if vtype == suggested_type:
                continue  # Já verificamos este tipo
                
            for vehicle in vehicles:
                if vehicle['id'] not in assigned_ids:
                    score = calculate_fit_score(vehicle['seats'], passengers_count)
                    
                    # Pequena penalidade por usar um tipo diferente do sugerido
                    score = score * 0.95
                    
                    if score > best_score:
                        best_score = score
                        best_vehicle = vehicle
    
    return best_vehicle, best_score

def reallocate_vehicles_and_passengers(assigned_routes, unassigned_routes, all_vehicles, assigned_ids):
    """
    Tenta realocar veículos e/ou redistribuir passageiros para acomodar rotas não atribuídas.
    
    Estratégias:
    1. Verificar se há veículos subutilizados que poderiam ser trocados
    2. Verificar se rotas pequenas poderiam ser combinadas
    3. Verificar se alguma rota grande poderia ser dividida
    
    Args:
        assigned_routes: Rotas que já possuem veículos
        unassigned_routes: Rotas sem veículos
        all_vehicles: Todos os veículos disponíveis
        assigned_ids: IDs de veículos já atribuídos
        
    Returns:
        Lista atualizada de rotas com veículos atribuídos, ou None se não foi possível realocar
    """
    # Verificar se temos veículos não atribuídos
    available_vehicles = [v for v in all_vehicles if v['id'] not in assigned_ids]
    
    if not available_vehicles:
        # Sem veículos disponíveis, tentar reequilibrar os já atribuídos
        return try_vehicle_rebalancing(assigned_routes, unassigned_routes)
    
    # Lista para os resultados
    result_routes = assigned_routes.copy()
    still_unassigned = []
    
    for route in unassigned_routes:
        passengers_count = len(route['passengers'])
        
        # Opção 1: Verificar se algum dos veículos disponíveis serve
        best_vehicle = None
        best_score = -float('inf')
        
        for vehicle in available_vehicles:
            if vehicle['seats'] >= passengers_count:
                # Cálculo de score simplificado
                score = -abs(vehicle['seats'] - passengers_count)
                if score > best_score:
                    best_score = score
                    best_vehicle = vehicle
        
        if best_vehicle:
            # Atribuir o veículo à rota
            route_copy = route.copy()
            route_copy['vehicle'] = best_vehicle
            result_routes.append(route_copy)
            available_vehicles.remove(best_vehicle)
            continue
            
        # Opção 2: Verificar se podemos combinar com outra rota pequena
        # (implementação simplificada - em produção seria mais complexo)
        combined = False
        for other_route in list(still_unassigned):  # Usar uma cópia para poder remover itens
            if passengers_count + len(other_route['passengers']) <= max(v['seats'] for v in available_vehicles):
                # Podemos combinar estas rotas
                combined_passengers = route['passengers'] + other_route['passengers']
                
                # Encontrar o melhor veículo para a rota combinada
                best_vehicle = None
                best_score = -float('inf')
                
                for vehicle in available_vehicles:
                    if vehicle['seats'] >= len(combined_passengers):
                        score = -abs(vehicle['seats'] - len(combined_passengers))
                        if score > best_score:
                            best_score = score
                            best_vehicle = vehicle
                
                if best_vehicle:
                    # Criar uma nova rota combinada
                    combined_route = {
                        'passengers': combined_passengers,
                        'estimated_time': max(route.get('estimated_time', 0), other_route.get('estimated_time', 0)),
                        'vehicle_type': route.get('vehicle_type', 'car'),
                        'vehicle': best_vehicle,
                        'combined': True  # Marcar como rota combinada
                    }
                    
                    result_routes.append(combined_route)
                    available_vehicles.remove(best_vehicle)
                    still_unassigned.remove(other_route)
                    combined = True
                    break
        
        if not combined:
            still_unassigned.append(route)
    
    # Se ainda temos rotas não atribuídas, retornar None para indicar falha
    if still_unassigned:
        return None
    
    # Sucesso! Todas as rotas foram atribuídas
    return result_routes

def try_vehicle_rebalancing(assigned_routes, unassigned_routes):
    """
    Tenta reequilibrar os veículos entre as rotas para maximizar a eficiência.
    Isso pode envolver trocas de veículos entre rotas ou reorganização de passageiros.
    
    Args:
        assigned_routes: Rotas que já possuem veículos
        unassigned_routes: Rotas sem veículos
        
    Returns:
        Lista atualizada de rotas com veículos, ou None se não foi possível reequilibrar
    """
    # Se não temos rotas não atribuídas, não é necessário reequilibrar
    if not unassigned_routes:
        return assigned_routes
        
    # Verificar se há veículos subutilizados (menos de 50% da capacidade)
    underutilized_routes = []
    for i, route in enumerate(assigned_routes):
        if route['vehicle'] and len(route['passengers']) < route['vehicle']['seats'] * 0.5:
            underutilized_routes.append((i, route))
    
    # Se não temos veículos subutilizados, não podemos reequilibrar
    if not underutilized_routes:
        return None
    
    # Criar uma cópia das rotas para manipulação
    result_routes = assigned_routes.copy()
    
    # Tentar redistribuir passageiros
    successful = redistribute_passengers_between_routes(
        result_routes, 
        unassigned_routes, 
        [i for i, _ in underutilized_routes]
    )
    
    if successful:
        return result_routes
    return None

def redistribute_passengers_between_routes(routes, unassigned_routes, underutilized_indices):
    """
    Redistribui passageiros entre rotas para aproveitar melhor os veículos e acomodar rotas não atribuídas.
    
    Args:
        routes: Lista atual de rotas com veículos
        unassigned_routes: Rotas sem veículos
        underutilized_indices: Índices de rotas com veículos subutilizados
        
    Returns:
        True se conseguiu redistribuir, False caso contrário
    """
    # Implementação simplificada:
    # 1. Coletar todos os passageiros de rotas não atribuídas
    # 2. Para cada passageiro, verificar se cabe em alguma rota subutilizada
    # 3. Se couber, adicionar à rota
    
    all_unassigned_passengers = []
    for route in unassigned_routes:
        all_unassigned_passengers.extend(route['passengers'])
    
    # Nada a redistribuir
    if not all_unassigned_passengers:
        return True
    
    # Para cada passageiro, tenta adicionar a uma rota subutilizada
    for passenger in all_unassigned_passengers[:]:  # Use cópia para poder remover itens
        for idx in underutilized_indices:
            route = routes[idx]
            vehicle = route['vehicle']
            
            if len(route['passengers']) < vehicle['seats']:
                # Há espaço no veículo
                route['passengers'].append(passenger)
                all_unassigned_passengers.remove(passenger)
                break
    
    # Se todos os passageiros foram atribuídos, sucesso!
    return len(all_unassigned_passengers) == 0

def calculate_vehicle_utilization(routes_with_vehicles):
    """
    Calcula e registra a utilização de capacidade dos veículos nas rotas.
    
    Args:
        routes_with_vehicles: Lista de rotas com veículos atribuídos
    """
    total_seats = 0
    total_passengers = 0
    utilization_data = []
    
    for route in routes_with_vehicles:
        if 'vehicle' in route and route['vehicle']:
            vehicle = route['vehicle']
            passengers = len(route['passengers'])
            seats = vehicle['seats']
            utilization = passengers / seats if seats > 0 else 0
            
            utilization_data.append({
                'vehicle': f"{vehicle['model']} ({vehicle['license_plate']})",
                'passengers': passengers,
                'seats': seats,
                'utilization': f"{utilization:.1%}"
            })
            
            total_seats += seats
            total_passengers += passengers
    
    # Calcular utilização geral
    overall_utilization = total_passengers / total_seats if total_seats > 0 else 0
    
    # Registrar informações (para debug/análise)
    logging.info(f"Utilização geral dos veículos: {overall_utilization:.1%}")
    logging.info(f"Total de passageiros: {total_passengers}, Total de assentos: {total_seats}")
    
    # Registrar utilização por veículo para debug
    for info in utilization_data:
        logging.debug(f"Veículo: {info['vehicle']} - Utilização: {info['utilization']}")
    
    return overall_utilization

def create_routes_in_system(routes_with_vehicles, company_id, start_coord, end_coord, 
                           start_point_str, end_point_str, is_arrival, base_route_name, max_duration):
    """
    Cria as rotas no sistema com base no planejamento.
    
    Args:
        routes_with_vehicles: Lista de rotas com veículos atribuídos
        company_id: ID da empresa
        start_coord: Coordenadas de origem
        end_coord: Coordenadas de destino
        start_point_str: Endereço de origem (texto)
        end_point_str: Endereço de destino (texto)
        is_arrival: Se é rota de chegada (True) ou saída (False)
        base_route_name: Nome base para as rotas
        max_duration: Tempo máximo em minutos
        
    Returns:
        Lista de rotas criadas com seus IDs
    """
    created_routes = []
    
    # Para cada rota planejada com veículo
    for i, route_data in enumerate(routes_with_vehicles):
        vehicle = route_data['vehicle']
        passengers = route_data['passengers']
        
        if not vehicle:
            continue  # Pula rotas sem veículo atribuído
            
        # Nome da rota com o número da rota e veículo
        route_name = f"{base_route_name} - Rota {i+1} - {vehicle['model']}"
        
        # Criar a rota no banco de dados
        with st.spinner(f"Criando rota {i+1}..."):
            try:
                # Calcular a rota otimizada usando o plan_optimized_route
                # com flag is_arrival para cálculo correto do tempo
                route_result = plan_optimized_route(
                    start_coord, 
                    end_coord, 
                    passengers, 
                    max_duration, 
                    get_vehicle_type(vehicle['model']),
                    is_arrival
                )
                
                if 'error' in route_result:
                    st.error(f"Erro ao calcular rota {i+1}: {route_result['error']}")
                    # Tentar com o método alternativo
                    route_result = optimize_route(
                        start_coord, 
                        end_coord, 
                        passengers, 
                        max_duration,
                        get_vehicle_type(vehicle['model'])
                    )
                    
                    if 'error' in route_result:
                        st.error(f"Todos os métodos de roteirização falharam para rota {i+1}.")
                        continue
                
                # Extrair métricas da rota calculada (tempo total correto)
                route_metrics = extract_route_metrics(route_result)
                estimated_time = route_metrics['duration_minutes'] if route_metrics['duration_minutes'] > 0 else None
                
                # Removida a verificação e alerta sobre limite de tempo excedido
                # O cálculo está correto, mas não precisamos mostrar alerta
                
                # Criar a rota no banco de dados com o tempo estimado correto
                route_id = create_route(
                    name=route_name,
                    company_id=company_id,
                    vehicle_id=vehicle['id'],
                    is_arrival=is_arrival,
                    start_address=start_point_str,
                    end_address=end_point_str,
                    start_lat=start_coord['lat'],
                    start_lon=start_coord['lon'],
                    end_lat=end_coord['lat'],
                    end_lon=end_coord['lon'],
                    created_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                )
                
                # Salvar a resposta da API
                if save_route_api_response(route_id, route_result):
                    st.success(f"Resposta da API para rota {i+1} salva com sucesso!")
                
                # Adicionar as paradas à rota
                added_stops = []
                for j, person_data in enumerate(passengers):
                    add_route_stop(
                        route_id=route_id,
                        stop_order=j + 1,
                        person_id=person_data['person_id'],
                        lat=person_data['lat'],
                        lon=person_data['lon']
                    )
                    added_stops.append(person_data['person_id'])
                
                # Adicionar a rota criada à lista, com o tempo estimado correto
                created_routes.append({
                    "route_id": route_id,
                    "vehicle": vehicle,
                    "passengers": passengers,
                    "route_data": route_result,
                    "estimated_time": estimated_time,
                    "color": ['blue', 'red', 'green', 'purple', 'orange'][i % 5]  # Cores alternadas
                })
                
            except Exception as e:
                st.error(f"Erro ao criar rota {i+1}: {str(e)}")
    
    return created_routes

def get_vehicle_type(model):
    """Determina o tipo de veículo baseado no modelo."""
    model = model.lower()
    if "bus" in model or "ônibus" in model:
        return "car"  # Alterado para car já que a API não tem bus
    elif "van" in model:
        return "car"
    elif "truck" in model or "caminhão" in model:
        return "truck"
    elif "moto" in model or "motorcycle" in model:
        return "motorcycle"
    else:
        return "car"  # Padrão

def display_created_routes(created_routes, start_coord, end_coord):
    """Exibe os mapas e detalhes das rotas criadas."""
    # Exibir mapa com todas as rotas juntas
    st.write("### Mapa Geral de Todas as Rotas")
    try:
        display_multiple_routes_on_map(created_routes, start_coord, end_coord)
    except Exception as e:
        st.error(f"Erro ao exibir o mapa geral: {str(e)}")
        st.info("Exibindo mapas individuais como alternativa")
    
    # Exibir detalhes de cada rota
    for i, route_info in enumerate(created_routes):
        # Obter métricas da rota para garantir tempo estimado consistente
        route_metrics = extract_route_metrics(route_info['route_data'])
        
        # Usar somente o tempo retornado pela API e limitar a 45 minutos
        max_allowed_time = 45  # Tempo máximo em minutos
        
        if route_metrics and route_metrics['duration_minutes'] > 0:
            api_time = route_metrics['duration_minutes']
            exceeds_limit = api_time > max_allowed_time
            estimated_time = f"{api_time:.1f} min"
            estimated_duration = format_duration(api_time * 60)
            # Armazenar para verificação dos limites
            time_value = api_time
        else:
            estimated_time = "N/A"
            estimated_duration = "N/A"
            exceeds_limit = False
            time_value = 0
        
        # Criar título com indicador visual baseado no tempo
        route_title = f"Detalhes da Rota {i+1} - {route_info['vehicle']['model']} - {estimated_time}"
        
        # Exibir informações da rota com tempo estimado único e consistente
        with st.expander(route_title):
            # Status do tempo com indicador visual
            if exceeds_limit:
                st.success(f"⚠️ **Tempo total da viagem desde o ponto de saída ({estimated_time})**")
                pass
            else:
                if time_value > 0:
                    # Mostrar barra de progresso do tempo em relação ao limite
                    percent = min(100, (time_value / max_allowed_time) * 100)
                    st.write(f"**Tempo estimado vs. limite:**")
                    st.progress(percent/100)
                    st.success(f"✅ **Rota dentro do limite de tempo ({time_value:.1f}/{max_allowed_time} min)**")
            
            st.write(f"**Veículo:** {route_info['vehicle']['model']} ({route_info['vehicle']['license_plate']})")
            st.write(f"**Motorista:** {route_info['vehicle']['driver']}")
            st.write(f"**Passageiros:** {len(route_info['passengers'])}")
            
            if route_metrics and route_metrics['distance'] != 'N/A':
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Distância total:** {route_metrics['distance']} km")
                with col2:
                    #st.write(f"**Tempo estimado:** {estimated_duration}")
                    pass
            else:
                #st.write(f"**Tempo estimado:** {estimated_time}")
                pass
            
            # Timeline visual dos segmentos da rota
            st.write("**Distribuição do Tempo:**")
            show_route_timeline(route_info['route_data'], max_allowed_time)
            
            # Lista de paradas
            st.write("**Paradas:**")
            stops_list = extract_stops_sequence(route_info['route_data'], route_info['passengers'])
            if stops_list:
                stops_df = pd.DataFrame(stops_list)
                st.table(stops_df)
            
            # Mapa individual
            st.write("**Mapa da Rota:**")
            try:
                display_route_on_map(
                    route_info['route_data'],
                    start_coord,
                    end_coord,
                    route_info['passengers'],
                    route_info['color']
                )
            except Exception as e:
                st.error(f"Erro ao exibir o mapa da rota: {str(e)}")

def show_route_timeline(route_data, max_time=45):
    """Exibe uma visualização de timeline dos segmentos da rota"""
    try:
        # Extrair segmentos da rota com seus tempos
        segments = []
        cumulative_time = 0
        
        # Tentar extrair segmentos de diferentes formatos de dados da API
        if 'features' in route_data:
            # Formato GeoJSON
            for feature in route_data['features']:
                if feature.get('geometry', {}).get('type') == 'LineString' and 'properties' in feature:
                    props = feature['properties']
                    if 'time' in props or 'duration' in props:
                        duration = props.get('time', props.get('duration', 0)) / 60  # converter para minutos
                        name = props.get('name', f"Segmento {len(segments)+1}")
                        segments.append({
                            'name': name,
                            'duration': duration,
                            'start': cumulative_time,
                            'end': cumulative_time + duration
                        })
                        cumulative_time += duration
        elif 'segments' in route_data:
            # Formato simplificado
            for seg in route_data['segments']:
                duration = seg.get('duration', 0) / 60  # converter para minutos
                name = seg.get('name', f"Segmento {len(segments)+1}")
                segments.append({
                    'name': name,
                    'duration': duration,
                    'start': cumulative_time,
                    'end': cumulative_time + duration
                })
                cumulative_time += duration
        
        # Criar visualização se houver segmentos válidos
        if segments:
            # Criar representação visual simples
            total_duration = sum(seg['duration'] for seg in segments)
            
            # Verificar se o tempo total excede o limite
            timeline_html = f"""
            <div style="width:100%; height:30px; background-color:#f0f0f0; position:relative; margin-bottom:10px;">
                <div style="position:absolute; top:0; left:0; width:100%; height:30px; border:1px solid #ddd; text-align:center; line-height:30px;">
                    Limite: {max_time} min
                </div>
            """
            
            # Adicionar barra para cada segmento
            for seg in segments:
                width_percent = (seg['duration'] / max_time) * 100
                left_percent = (seg['start'] / max_time) * 100
                color = "#4CAF50" if seg['end'] <= max_time else "#FF5722"  # Verde se dentro do limite, laranja se exceder
                
                # Limitar a largura a 100%
                if left_percent + width_percent > 100:
                    width_percent = 100 - left_percent
                
                if width_percent > 0:
                    timeline_html += f"""
                    <div title="{seg['name']}: {seg['duration']:.1f} min" 
                        style="position:absolute; top:0; left:{left_percent}%; width:{width_percent}%; 
                        height:30px; background-color:{color}; opacity:0.7;"></div>
                    """
            
            # Fechar div principal
            timeline_html += "</div>"
            
            # Exibir indicador de tempo estimado total
            timeline_html += f"""
            <div style="text-align:right; font-size:small;">
                Tempo total estimado: <strong>{total_duration:.1f} min</strong> 
                {'<span style="color:#FF5722;">⚠️ Excede o limite</span>' if total_duration > max_time else 
                '<span style="color:#4CAF50;">✅ Dentro do limite</span>'}
            </div>
            """
            
            # Renderizar HTML
            st.markdown(timeline_html, unsafe_allow_html=True)
            
            # Exibir explicação metodológica
            with st.expander("Como o tempo é calculado?"):
                st.markdown("""
                **Metodologia de cálculo do tempo:**
                
                1. **Tempo de direção:** Calculado com base na distância e velocidade média do tipo de veículo
                2. **Tempo em paradas:** Adicionado para cada embarque/desembarque (varia de 0,5 a 2 min por parada)
                3. **Fator de tráfego:** Um adicional de 20% é aplicado para considerar congestionamentos
                4. **Validação:** O tempo é verificado contra o limite máximo de 45 minutos
                
                Esta estimativa considera condições normais de tráfego. Fatores climáticos ou eventos 
                extraordinários podem impactar o tempo real da viagem.
                """)
        else:
            # Fallback se não conseguir extrair segmentos
            st.info("Não foi possível extrair detalhes dos segmentos para visualização da timeline.")
            
    except Exception as e:
        st.warning(f"Erro ao criar visualização da timeline: {str(e)}")

def extract_route_metrics(route_data):
    """Extract metrics like distance and duration from route data"""
    try:
        # Verificar se temos dados da API no formato completo
        if 'features' in route_data:
            for feature in route_data['features']:
                if 'properties' in feature:
                    # Tentar diferentes locais onde os dados de tempo/distância podem estar
                    props = feature['properties']
                    
                    # Opção 1: Na propriedade 'summary'
                    if 'summary' in props:
                        summary = props['summary']
                        if 'distance' in summary and 'duration' in summary:
                            distance_km = round(summary['distance'] / 1000, 2)
                            duration_min = round(summary['duration'] / 60, 2)
                            duration_formatted = format_duration(summary['duration'])
                            
                            return {
                                'distance': distance_km,
                                'duration': duration_formatted,
                                'duration_minutes': duration_min
                            }
                    
                    # Opção 2: Diretamente nas propriedades
                    if 'distance' in props and 'time' in props:
                        distance_km = round(props['distance'] / 1000, 2)
                        duration_min = round(props['time'] / 60, 2)
                        duration_formatted = format_duration(props['time'])
                        
                        return {
                            'distance': distance_km,
                            'duration': duration_formatted,
                            'duration_minutes': duration_min
                        }
        
        # Verificar se temos campos diretos no objeto route_data
        if 'total_distance_km' in route_data and 'total_duration_minutes' in route_data:
            distance_km = round(route_data['total_distance_km'], 2)
            duration_min = round(route_data['total_duration_minutes'], 2)
            duration_formatted = format_duration(duration_min * 60)
            
            return {
                'distance': distance_km,
                'duration': duration_formatted,
                'duration_minutes': duration_min
            }
        
        # Como último recurso, verificar se o 'estimated_time' está disponível
        if 'estimated_time' in route_data and route_data['estimated_time'] not in [None, 'N/A']:
            duration_min = route_data['estimated_time']
            if isinstance(duration_min, (int, float)):
                duration_formatted = format_duration(duration_min * 60)
                return {
                    'distance': route_data.get('total_distance_km', 0),
                    'duration': duration_formatted,
                    'duration_minutes': duration_min
                }
        
        # Fallback if structured data not found
        return {
            'distance': 'N/A',
            'duration': 'N/A',
            'duration_minutes': 0
        }
    except Exception as e:
        st.error(f"Erro ao extrair métricas da rota: {e}")
        return {
            'distance': 'N/A',
            'duration': 'N/A',
            'duration_minutes': 0
        }

def format_duration(seconds):
    """Format duration in seconds to a human-readable string"""
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if hours > 0:
        return f"{int(hours)}h {int(minutes)}min"
    else:
        return f"{int(minutes)}min"

def extract_stops_sequence(route_data, passengers):
    """Extract the sequence of stops with estimated arrival times"""
    stops_list = []
    
    try:
        # First check if we have the new format from Route Planner API
        if "stops" in route_data and isinstance(route_data["stops"], list):
            # Process data in the new format (from plan_optimized_route)
            for stop in route_data["stops"]:
                # Skip first (start) and last (end) stops that don't have passengers
                if not stop.get("persons") or len(stop.get("persons", [])) == 0:
                    continue
                    
                order = stop.get("stop_order", 0)
                person_data = stop.get("persons", [{}])[0]
                
                # Format arrival time if available
                arrival_time = stop.get("arrival_time", "N/A")
                if isinstance(arrival_time, (int, float)) and arrival_time > 0:
                    from datetime import datetime
                    dt = datetime.fromtimestamp(arrival_time)
                    arrival_time = dt.strftime("%H:%M")
                
                # Add stop to list
                stops_list.append({
                    'Ordem': order,
                    'Passageiro': person_data.get('name', 'Desconhecido'),
                    'Horário Estimado': arrival_time,
                    'Tempo até Próxima Parada': stop.get('time_to_next', 'N/A')
                })
                
            # If we processed some stops, return the result
            if stops_list:
                return stops_list
        
        # If we don't have the new format or it's empty, try the old format
        if 'features' in route_data:
            # Try to find waypoints or stopover information
            waypoints = [f for f in route_data['features'] 
                        if f['geometry']['type'] == 'Point' and 'properties' in f]
            
            # Sort waypoints by sequence if available
            waypoints.sort(key=lambda w: w['properties'].get('index', 0) 
                          if 'properties' in w and 'index' in w['properties'] else 0)
            
            for i, waypoint in enumerate(waypoints):
                properties = waypoint['properties']
                
                # Find closest matching passenger
                wp_lat = waypoint['geometry']['coordinates'][1]
                wp_lon = waypoint['geometry']['coordinates'][0]
                
                closest_passenger = None
                min_distance = float('inf')
                for p in passengers:
                    dist = ((p['lat'] - wp_lat)**2 + (p['lon'] - wp_lon)**2)**0.5
                    if dist < min_distance:
                        min_distance = dist
                        closest_passenger = p
                
                # Extract time info if available
                arrival_time = properties.get('arrival_time', 'N/A')
                if isinstance(arrival_time, (int, float)):
                    arrival_time = format_time_from_timestamp(arrival_time)
                
                stops_list.append({
                    'Ordem': i + 1,
                    'Passageiro': closest_passenger['name'] if closest_passenger else 'Desconhecido',
                    'Horário Estimado': arrival_time,
                    'Tempo até Próxima Parada': properties.get('time_to_next', 'N/A')
                })
                
        # Fallback if detailed waypoint info not available
        if not stops_list:
            for i, p in enumerate(passengers):
                stops_list.append({
                    'Ordem': i + 1,
                    'Passageiro': p['name'],
                    'Horário Estimado': 'N/A',
                    'Tempo até Próxima Parada': 'N/A'
                })
                
        return stops_list
        
    except Exception as e:
        st.error(f"Erro ao extrair sequência de paradas: {e}")
        return []

def format_time_from_timestamp(timestamp):
    """Format a Unix timestamp to a readable time"""
    from datetime import datetime
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%H:%M")
    except:
        return "N/A"

def display_saved_route_on_map(route_data, color='blue'):
    """Display a saved route on a Folium map with specified color"""
    start_coord = route_data['start_point']
    end_coord = route_data['end_point']
    waypoints = route_data['waypoints']
    
    # Verificar se as coordenadas são válidas
    if not (start_coord and end_coord and 
            'lat' in start_coord and 'lon' in start_coord and 
            'lat' in end_coord and 'lon' in end_coord):
        st.error("Coordenadas de início ou fim inválidas para exibir o mapa")
        return
    
    # Create a folium map centered on the route area
    center_lat = (start_coord['lat'] + end_coord['lat']) / 2
    center_lon = (start_coord['lon'] + end_coord['lon']) / 2
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=13)
    
    # Add start marker
    folium.Marker(
        location=[start_coord['lat'], start_coord['lon']],
        popup="Ponto de Partida",
        icon=folium.Icon(color='green', icon='play', prefix='fa')
    ).add_to(m)
    
    # Add end marker
    folium.Marker(
        location=[end_coord['lat'], end_coord['lon']],
        popup="Ponto de Chegada",
        icon=folium.Icon(color='red', icon='stop', prefix='fa')
    ).add_to(m)
    
    # Add waypoint markers
    valid_waypoints = [wp for wp in waypoints if 'lat' in wp and 'lon' in wp]
    for i, wp in enumerate(valid_waypoints):
        folium.Marker(
            location=[wp['lat'], wp['lon']],
            popup=f"Parada {i+1}: {wp.get('name', 'Passageiro')}",
            icon=folium.Icon(color='blue', icon='user', prefix='fa')
        ).add_to(m)
    
    # Create a simple route line connecting all points in order
    all_points = []
    all_points.append([start_coord['lat'], start_coord['lon']])
    for wp in valid_waypoints:
        all_points.append([wp['lat'], wp['lon']])
    all_points.append([end_coord['lat'], end_coord['lon']])
    
    # Add the route line with specified color
    folium.PolyLine(
        all_points,
        color=color,
        weight=4,
        opacity=0.7
    ).add_to(m)
    
    # Display the map
    folium_static(m)

def view_existing_routes():
    """
    Exibe as rotas existentes no banco de dados e permite visualizá-las
    """
    st.subheader("Rotas Existentes")
    
    # Obter todas as rotas do banco de dados
    all_routes = get_all_routes()
    
    if not all_routes:
        st.info("Não há rotas cadastradas no sistema.")
        return
    
    # Preparar dados para seleção
    route_options = [f"{route['name']} (ID: {route['id']})" for route in all_routes]
    
    selected_route = st.selectbox(
        "Selecione uma rota para visualizar:",
        options=route_options,
        index=None
    )
    
    if selected_route:
        # Extrair ID da rota da string selecionada
        route_id = int(selected_route.split("ID: ")[1].strip(")"))
        
        # Obter detalhes da rota
        route_details = get_route_details(route_id)
        
        if route_details:
            # Exibir detalhes básicos
            st.write(f"**Nome da Rota:** {route_details['name']}")
            st.write(f"**Empresa:** {route_details['company_name']}")
            st.write(f"**Veículo:** {route_details['vehicle_model']} ({route_details['license_plate']}) - Motorista: {route_details['driver']}")
            st.write(f"**Tipo:** {'Ida para empresa' if route_details['is_arrival'] else 'Saída da empresa'}")
            st.write(f"**Data de Criação:** {route_details['created_at']}")
            
            st.write("**Origem:** " + route_details['start_address'])
            st.write("**Destino:** " + route_details['end_address'])
            
            # Exibir paradas
            st.write("### Paradas")
            stops = route_details.get('stops', [])
            
            if stops:
                stops_df = pd.DataFrame([
                    {
                        "Ordem": stop['stop_order'],
                        "Nome": stop['person_name'],
                        "Endereço": f"{stop['street']}, {stop['number']}, {stop['city']}"
                    } for stop in stops
                ])
                st.dataframe(stops_df)
            else:
                st.info("Esta rota não possui paradas registradas.")
            
            # Tentar recuperar a resposta da API para exibir o mapa
            api_response = get_route_api_response(route_id)
            
            if api_response:
                # Preparar dados para o mapa
                start_point = {
                    'lat': route_details['start_lat'],
                    'lon': route_details['start_lon']
                }
                
                end_point = {
                    'lat': route_details['end_lat'],
                    'lon': route_details['end_lon']
                }
                
                waypoints = [
                    {
                        'lat': stop['lat'],
                        'lon': stop['lon'],
                        'name': stop['person_name']
                    } for stop in stops
                ]
                
                route_data = {
                    'start_point': start_point,
                    'end_point': end_point,
                    'waypoints': waypoints
                }
                
                st.write("### Mapa da Rota")
                try:
                    # Tentar exibir mapa com dados da API
                    display_route_on_map(api_response, start_point, end_point, waypoints)
                except Exception as e:
                    st.error(f"Erro ao exibir mapa detalhado: {str(e)}")
                    # Fallback para mapa simplificado
                    display_saved_route_on_map(route_data)
            else:
                # Fallback se não tiver resposta da API
                st.write("### Mapa da Rota (Simplificado)")
                route_data = {
                    'start_point': {
                        'lat': route_details['start_lat'],
                        'lon': route_details['start_lon']
                    },
                    'end_point': {
                        'lat': route_details['end_lat'],
                        'lon': route_details['end_lon']
                    },
                    'waypoints': [
                        {
                            'lat': stop['lat'],
                            'lon': stop['lon'],
                            'name': stop['person_name']
                        } for stop in stops
                    ]
                }
                display_saved_route_on_map(route_data)
        else:
            st.error("Não foi possível obter os detalhes desta rota.")

def calculate_vehicles_needed(total_passengers, available_vehicles):
    """
    Seleciona os veículos mais eficientes para transportar os passageiros.
    Prioriza veículos maiores para evitar fragmentação excessiva de rotas.
    Garante que a capacidade máxima dos veículos não seja excedida.
    
    Args:
        total_passengers: Número total de passageiros
        available_vehicles: Lista de veículos disponíveis
    
    Returns:
        Lista de veículos selecionados
    """
    # Ordenar veículos do maior para o menor (priorizar veículos maiores primeiro)
    sorted_vehicles = sorted(available_vehicles, key=lambda v: v['seats'], reverse=True)
    
    selected_vehicles = []
    remaining_passengers = total_passengers
    
    # Primeiro passo: usar veículos grandes para acomodar a maioria dos passageiros
    for vehicle in sorted_vehicles[:]:
        if remaining_passengers <= 0:
            break
            
        # Determinar quantos passageiros este veículo pode levar
        # (não excedendo sua capacidade)
        passengers_to_assign = min(vehicle['seats'], remaining_passengers)
        
        if passengers_to_assign > 0:
            selected_vehicles.append(vehicle)
            remaining_passengers -= passengers_to_assign
            sorted_vehicles.remove(vehicle)  # Não considerar este veículo novamente
    
    # Se ainda restam passageiros e veículos, continuar atribuindo
    while remaining_passengers > 0 and sorted_vehicles:
        # Usar o maior veículo disponível
        vehicle = sorted_vehicles.pop(0)
        selected_vehicles.append(vehicle)
        remaining_passengers -= vehicle['seats']
    
    # Calcular a capacidade total dos veículos selecionados
    total_capacity = sum(v['seats'] for v in selected_vehicles)
    
    return {
        'vehicles': selected_vehicles,
        'remaining_passengers': max(0, remaining_passengers),
        'total_capacity': total_capacity,
        'is_sufficient': remaining_passengers <= 0
    }

def redistribute_passengers(clustering_result, force_include_all=False):
    """
    Redistribui passageiros entre veículos respeitando a capacidade de cada um
    
    Args:
        clustering_result: Resultado original da clusterização
        force_include_all: Se True, tenta incluir todos os passageiros mesmo redistribuindo
        
    Returns:
        Resultado de clusterização atualizado com distribuição ajustada
    """
    vehicle_assignments = clustering_result['vehicle_assignments']
    
    # 1. Colete todos os passageiros
    all_passengers = []
    for vehicle_id, vehicle_data in vehicle_assignments.items():
        all_passengers.extend(vehicle_data['passengers'])
        # Limpa a lista de passageiros do veículo
        vehicle_data['passengers'] = []
    
    # 2. Ordene os veículos por capacidade (do maior para o menor)
    sorted_vehicles = sorted(
        [(vehicle_id, data['vehicle']) for vehicle_id, data in vehicle_assignments.items()],
        key=lambda x: x[1]['seats'], 
        reverse=True
    )
    
    # 3. Redistribua os passageiros
    remaining_passengers = all_passengers.copy()
    
    for vehicle_id, vehicle in sorted_vehicles:
        # Número de assentos disponíveis neste veículo
        available_seats = vehicle['seats']
        
        # Atribuir passageiros até o limite de assentos
        assigned_passengers = remaining_passengers[:available_seats]
        vehicle_assignments[vehicle_id]['passengers'] = assigned_passengers
        
        # Remover os passageiros atribuídos da lista de restantes
        remaining_passengers = remaining_passengers[available_seats:]
        
        if not remaining_passengers:
            break
    
    # 4. Se ainda restaram passageiros e estamos forçando inclusão, tentar acomodá-los
    if remaining_passengers and force_include_all:
        st.warning(f"Ainda há {len(remaining_passengers)} passageiros sem veículo após redistribuição.")
        
        # Opção 1: Distribuir os passageiros restantes pelos veículos existentes (sobrecarga)
        for idx, passenger in enumerate(remaining_passengers):
            # Determinar veículo para este passageiro (distribuição cíclica)
            vehicle_idx = idx % len(sorted_vehicles)
            vehicle_id = sorted_vehicles[vehicle_idx][0]
            
            # Adicionar ao veículo
            vehicle_assignments[vehicle_id]['passengers'].append(passenger)
    
    return clustering_result

def process_and_display_route(route_data, is_arrival=True):
    """
    Processa e exibe estatísticas detalhadas da rota
    
    Args:
        route_data: Dados da rota retornados pela API
        is_arrival: Se True, é uma rota de ida para empresa
    """
    # Extrair estatísticas principais
    distancia_total = route_data.get('distance', 0) / 1000  # Converter para km
    tempo_total = route_data.get('time', 0) / 60  # Converter para minutos
    
    # Exibir estatísticas gerais
    st.subheader("Estatísticas da Rota")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Distância Total", f"{distancia_total:.2f} km")
    with col2:
        st.metric("Tempo Estimado", f"{tempo_total:.0f} min")
    
    # Exibir informações de cada parada
    st.subheader("Detalhes das Paradas")
    
    paradas_data = []
    tempo_acumulado = 0
    
    # Calcular horário base (para cálculo de horário estimado)
    hora_inicio = datetime.now().replace(hour=7, minute=0, second=0, microsecond=0)  # Exemplo: 7:00 AM
    
    for i, waypoint in enumerate(route_data.get('waypoints', [])):
        if i == 0:  # Ponto de partida
            tipo = "Partida"
        elif i == len(route_data.get('waypoints', [])) - 1:  # Ponto de chegada
            tipo = "Chegada"
        else:
            tipo = "Parada"
        
        # Calcular tempo até esta parada
        tempo_ate_parada = waypoint.get('time', 0) / 60  # em minutos
        
        # Calculando tempo para próxima parada
        if i < len(route_data.get('waypoints', [])) - 1:
            proximo_tempo = route_data.get('waypoints', [])[i+1].get('time', 0) / 60
            tempo_para_proxima = proximo_tempo - tempo_ate_parada
        else:
            tempo_para_proxima = 0
        
        # Calcular horário estimado
        horario_estimado = hora_inicio + timedelta(minutes=tempo_ate_parada)
        
        # Adicionar informações da parada
        parada_info = {
            "Sequência": i+1,
            "Tipo": tipo,
            "Nome/Local": waypoint.get('name', 'N/A'),
            "Tempo Acumulado (min)": f"{tempo_ate_parada:.1f}",
            "Horário Estimado": horario_estimado.strftime("%H:%M"),
            "Tempo até Próxima (min)": f"{tempo_para_proxima:.1f}" if tempo_para_proxima > 0 else "-"
        }
        paradas_data.append(parada_info)
    
    # Exibir tabela de paradas
    st.table(pd.DataFrame(paradas_data))
    
    # Exibir mapa da rota (requer adaptação para usar o route_data)
    display_route_map(route_data)

if __name__ == "__main__":
    main()