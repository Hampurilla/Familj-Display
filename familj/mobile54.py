"""One stable, private URL for Wi-Fi and cellular. No public tunnelling."""
from __future__ import annotations

def register_mobile(app, store, boot):
    from flask import Blueprint,render_template,jsonify,request
    if 'familj_mobile54' in app.extensions:
        return
    app.extensions['familj_mobile54']=True
    bp=Blueprint('familj_mobile54',__name__)
    reader=app.extensions['familj_remote']

    def snapshot():
        data=reader.get(store.settings()['pin_enabled'])
        # No invented hostname or user-entered redirect URL.
        data['current_url']=data.get('url')
        return data

    @bp.get('/admin/mobile')
    def page():
        return render_template('mobile54.html',boot=boot('admin'),remote=snapshot())

    @bp.get('/admin/mobile/status')
    def status():
        return jsonify(snapshot())

    @bp.get('/mobile.webmanifest')
    def manifest():
        data=dict(id='/admin',name='Familj Display',short_name='Hemma',lang='sv',
            start_url='/admin',scope='/admin',display='standalone',
            background_color='#f2efe6',theme_color='#f2efe6',
            icons=[dict(src='/static/homevoice-icon-192.png',sizes='192x192',type='image/png'),
                   dict(src='/static/homevoice-icon-512.png',sizes='512x512',type='image/png')])
        response=jsonify(data);response.mimetype='application/manifest+json'
        return response

    @app.after_request
    def identify(response):
        if request.path=='/health' and response.status_code==200 and response.is_json:
            data=response.get_json();data['homevoice_version']='5.4.0';response.set_data(app.json.dumps(data))
        return response
    app.register_blueprint(bp)
