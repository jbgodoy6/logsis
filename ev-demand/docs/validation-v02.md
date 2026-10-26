# EnergyCube D-Max v0.2 — validação em 26/10/2026

Adicionadas identidade EnergyCube/D-Max e página de multimedidor com configuração manual TCP/IP e RS485/RTU.

- 44 testes automatizados no Linux x86-64, Python 3.12.
- Mantidos os testes de controle, segurança, filas, prioridade e fluxo OCPP 1.6J com dois clientes WebSocket.
- Mapa TCP com vários endereços, funções 03/04 e conversão base 1 → offset de protocolo.
- Tipos de 16/32/64 bits, float32/64, escala e quatro combinações de ordem de palavras/bytes.
- CRC RTU, exceções Modbus e rejeição de frames corrompidos, NaN, limites de endereço e grandezas duplicadas.
- Driver pyserial real com pseudo-terminal Linux, respondedor RTU de teste e validação do quadro enviado.
- Migração do mapa v0.1, persistência de COM/baud/paridade, requisito de potência total e teste de leitura sem salvar o formulário.
- Navegador Chromium: logo e paleta, navegação, TCP/RTU, endereços manuais reais enviados a um respondedor TCP, resultados e salvamento do mapa.
- Desktop e celular sem erros de JavaScript e sem transbordamento horizontal da página. O mapa tem rolagem horizontal interna no celular.

Os ensaios não utilizaram multimedidor, adaptador RS485 ou carregador físico. Windows, Raspberry/ARM64, hardware, ensaio prolongado de 60 conexões e integração de nuvem/Grafana continuam pendentes. Limites de corrente por fase ainda não são aplicados pelo controlador; as correntes são leituras auxiliares disponíveis no diagnóstico.

O logo foi preparado em PNG a partir da referência visual recebida, com transparência para a interface; não é o arquivo vetorial original.
