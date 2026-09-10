from nicegui import ui

@ui.page('/')
def index():
    ui.label('Hello')

ui.run(host='0.0.0.0', port=8080, reload=False, show=False, favicon=None)