"""Fluxos reais no Chromium instalado, com câmera simulada e banco temporário."""
import os
from pathlib import Path
import threading

import pytest
from werkzeug.serving import make_server

playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture
def live_server(application):
    server = make_server("127.0.0.1", 0, application, threaded=True)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    worker.join(timeout=5)


@pytest.fixture
def browser():
    candidates = [os.environ.get("CHROME_PATH", ""),
                  r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                  r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]
    executable = next((path for path in candidates if path and Path(path).is_file()), None)
    with playwright.sync_playwright() as manager:
        options = {"headless": True, "args": ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"]}
        if executable:
            options["executable_path"] = executable
        browser = manager.chromium.launch(**options)
        yield browser
        browser.close()


def enter(page, live_server, role="admin"):
    page.goto(live_server)
    page.get_by_label("Usuário", exact=True).fill(role)
    page.get_by_label("Senha", exact=True).fill("senha-teste-123")
    page.get_by_role("button", name="Entrar", exact=True).click()
    page.get_by_role("button", name="Atualizar", exact=True).wait_for()


def sign(page, name):
    page.locator('#sigName').fill(name)
    page.locator('#capture:not([disabled])').wait_for()
    page.locator('#capture').click()
    canvas = page.locator('#sigCanvas')
    canvas.scroll_into_view_if_needed()
    box = canvas.bounding_box()
    page.mouse.move(box['x'] + 20, box['y'] + 70)
    page.mouse.down()
    for x, y in ((70, 30), (110, 90), (170, 35), (230, 80)):
        page.mouse.move(box['x'] + x, box['y'] + y, steps=6)
    page.mouse.up()
    page.get_by_role('button', name='Confirmar', exact=True).click()
    page.locator('#sigOverlay').wait_for(state='detached')


def no_horizontal_overflow(page):
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')


def test_mobile_emission_signature_invalidation_close_pdf(browser, live_server, tmp_path):
    context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                                  has_touch=True, device_scale_factor=2, permissions=["camera"],
                                  accept_downloads=True)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    enter(page, live_server)
    no_horizontal_overflow(page)
    page.get_by_role('button', name='Nova PTS').click()
    page.get_by_role('button', name='Trabalho em Altura', exact=True).click()
    page.get_by_label('Empresa executante', exact=True).fill('UNIVESP')
    page.get_by_label('Local / Setor', exact=True).fill('Galpão de teste móvel')
    today = page.get_by_label('Data de emissão', exact=True).input_value()
    page.get_by_label('Validade — início', exact=True).fill(today+'T08:00')
    page.get_by_label('Validade — fim', exact=True).fill(today+'T10:00')
    page.get_by_label('Descrição do trabalho', exact=True).fill('Inspeção simulada no protótipo')
    page.get_by_label('Equipe executante (um nome por linha)', exact=True).fill('Pessoa Um\nPessoa Dois')
    for checkbox in page.locator('input[type=checkbox]').all():
        checkbox.check()
    page.locator('[data-action=sign][data-role=emitente]').click()
    sign(page, 'Pessoa Emitente')
    page.get_by_label('Local / Setor', exact=True).fill('Galpão revisado')
    assert page.locator('#signatures img').count() == 0
    assert page.locator('#emit').is_disabled()
    page.screenshot(path=str(tmp_path/'mobile-form.png'), full_page=True)
    for role in ('emitente', 'executante', 'supervisor'):
        page.locator(f'[data-action=sign][data-role={role}]').click()
        sign(page, 'Pessoa '+role)
    assert page.locator('#emit').is_enabled()
    # Último campo editado atualiza o estado sem precisar clicar em outro controle.
    page.get_by_label('Local / Setor', exact=True).fill('')
    assert page.locator('#emit').is_disabled()
    page.get_by_label('Local / Setor', exact=True).fill('Galpão final')
    for role in ('emitente', 'executante', 'supervisor'):
        page.locator(f'[data-action=sign][data-role={role}]').click()
        sign(page, 'Pessoa '+role)
    page.locator('#emit').click()
    page.get_by_role('heading', name='Galpão final', exact=True).wait_for()
    no_horizontal_overflow(page)
    with page.expect_download() as event:
        page.get_by_role('button', name='Baixar PDF', exact=True).click()
    assert event.value.suggested_filename.endswith('.pdf')
    page.get_by_role('button', name='Encerrar PTS', exact=True).click()
    sign(page, 'Pessoa Encerramento')
    page.get_by_role('button', name='Encerrar PTS', exact=True).wait_for(state='detached')
    page.screenshot(path=str(tmp_path/'mobile-detail.png'), full_page=True)
    page.get_by_role('button', name='Voltar à lista', exact=True).click()
    search = page.get_by_role('searchbox')
    search.fill('Galpão')
    page.wait_for_timeout(500)
    assert search.input_value() == 'Galpão'
    assert search.evaluate('(el)=>el === document.activeElement')
    assert page.locator('.pts-card').count() == 1
    assert not errors, errors
    context.close()


@pytest.mark.parametrize('width', [320, 768, 1440])
def test_login_and_consultation_layout(browser, live_server, width):
    context=browser.new_context(viewport={"width":width,"height":900})
    page=context.new_page()
    enter(page,live_server,'consulta')
    no_horizontal_overflow(page)
    assert page.get_by_role('button',name='Nova PTS').count()==0
    page.get_by_role('button',name='Sair',exact=True).click()
    page.get_by_role('button',name='Entrar',exact=True).wait_for()
    no_horizontal_overflow(page)
    context.close()
