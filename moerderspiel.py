import os
import sys
workdir = os.path.dirname(__file__)
modpath = os.path.join(workdir,"lib")
sys.path.insert(0,modpath)
from flask import Flask, request as req, redirect, url_for, make_response, render_template
import time
from urllib.parse import quote_plus
import pickle
import codecs
import os.path
import shutil
import utils 
import filelock
import logging
import time
import locale
import wordconstruct
import moerderklassen
from moerderklassen import GameError
from moerdergraph import moerdergraph
from moerdergraphall import moerdergraphall
from pprint import pformat
from functools import wraps
#from moerderspiel import _url, _savegame
locale.setlocale(locale.LC_ALL, ('de_DE', 'UTF8'))
os.environ['TZ'] = 'Europe/Berlin'
time.tzset()

app = Flask(__name__)

utils.url_for = url_for # type: ignore

# G als Objekt für globale Pfade und Hilfsfunktionen
class G:
    def __init__(self):
        self.fname = ''
        self.lockfile: filelock.FileLock | None = None
        self.workdir = workdir
        self.modpath = modpath
        self.staticdir = os.path.join(workdir, 'static')
        self.cssdir = os.path.join(self.staticdir, 'css')
        self.imagedir = os.path.join(self.staticdir, 'images')
        self.templatedir = os.path.join(workdir, 'templates')
        self.savegamedir = os.path.join(workdir, 'savegames')
    @staticmethod
    def u8(s):
        if isinstance(s, bytes):
            try:
                return s.decode('utf8')
            except UnicodeDecodeError:
                try:
                    return s.decode('latin1')
                except UnicodeDecodeError:
                    return None
        if isinstance(s,str):
            return s
g = G()

def route(part, altpart=None, *arg, **kwarg):
	def func_wrapper(f):
		x = altpart 		# hack to avoid "usage of variable before assignment" error...
		if x is None:
			x = part + '/' + '/'.join([ "<%s>" % n for n in f.__code__.co_varnames[0:f.__code__.co_argcount]])
		if x.find('<') >= 0:
			if 'methods' in kwarg:
				kwarg['methods'].append('POST')
			else:
				kwarg['methods'] = ['GET', 'POST']
		@app.route(x, *arg, **kwarg)
		@app.route(part, *arg, **kwarg)
		@wraps(f)
		def handler(*args, **kwargs):
			if len(kwargs) == 0:
				if len(req.args) > 0:
					a = dict([ (k,v) for k,v in req.args.items() ])
				else:
					a = dict([ (k,v) for k,v in req.form.items() ])
			else:
				a = kwargs 
			return f(**a)
		return handler
	return func_wrapper

def _loadgame(gameid, lock=True):
    g.fname = os.path.join(g.savegamedir, '%s.pkl' % gameid)
    g.lockfile = filelock.FileLock('%s.lock' )
    while g.lockfile.acquire():
        pass
    
    input = open(g.fname, 'rb')
    try:
        ret = pickle.load(input)
    except Exception as e:
        print(f'{e}')
        raise
    input.close()
    if not lock:
        g.lockfile.release()
        del g.lockfile
    ret.workdir = g.workdir
    ret.templatedir = g.templatedir
    ret.savegamedir = g.savegamedir
    os.environ['TZ'] = ret.config.timezone
    time.tzset()
    return ret

def _response(content, content_type="text/html"):
    response = make_response(content)
    response.content_type = content_type
    print(content)
    return response

def _mainstream(filename, **args):
	if 'errormsg' not in args:
		args['errormsg'] = ''
	# mainframe.html muss auf Jinja2 umgestellt sein!
	return render_template('mainframe.html', baseurl=url_for('.index'), url_for=url_for, content=render_template(filename, **args), **args)



def _ajaxstream(filename, selectors, **args):
    """Creates a Jinja2-based response containing XML data for AJAX updates.

    Args:
        filename (str): The template file to render.
        selectors (list or str): List of element IDs to update.
        **args: Additional context variables for the template.

    Returns:
        Response: A Flask response object with the rendered XML.
    """
    from flask import render_template_string

    # Render the full template with the provided arguments
    full_content = render_template(filename, **args)

    # Extract specific parts based on selectors
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(full_content, 'html.parser')

    selected_content = []
    if isinstance(selectors, str):
        selectors = [selectors]

    for selector in selectors:
        element = soup.select_one(selector)
        if element:
            selected_content.append(str(element))

    # Combine selected content into a single XML response
    response_content = "<div xmlns=\"http://www.w3.org/1999/xhtml\">" + "".join(selected_content) + "</div>"

    return _response(response_content, content_type="text/xml")

def _savegame(game, checkifexists=False):
	g.fname = os.path.join(g.savegamedir, '%s.pkl' % game.id)
	if checkifexists and os.path.isfile(g.fname):
		#raise AssertionError
		pass
	output = open('%s.tmp' % g.fname, 'wb')
	pickle.dump(game, output)
	output.close()
	os.rename('%s.tmp' % g.fname, g.fname)
	if hasattr(g, 'lockfile'):
		g.lockfile.release()
		del g.lockfile
	return game.id
	

def _url(req, action, id=None, errormsg=""):
	if id is not None and action == 'view' and len(errormsg) < 2:
		# I can do this because .htaccess has this line: 
		# RewriteRule ^([a-z0-9]+)$ /moerderspiel/view?id=$1 [R=302]
		return "%s%s" % (req.host_url, id)
	else:
		url = "%s%s" % (url_for('.index'), action)
		if id != None:
			url += '?id=' + id
		if len(errormsg) > 1 and id == None:
			url +=  '?msg=' + quote_plus(errormsg)
		elif len(errormsg) > 1:
			url +=  '&msg=' + quote_plus(errormsg)
		return url



def _pdfgen(game):
	return game.pdfgen()


def _pdfblankgen(count, game):
	tmptexdir = "/tmp/moerder_" + game.id
	if not os.path.isdir(tmptexdir):
		os.mkdir(tmptexdir)
	shutil.copyfile(os.path.join(g.templatedir, "moerder.tex"), os.path.join(tmptexdir, "moerder.tex"))
	listfile = codecs.open(os.path.join(tmptexdir, "list.tex"), "w", "utf-8")
	for p in range(0, count):
		for roundid in sorted(game.rounds):
			round = game.rounds[roundid]
			roundname = round.name if len(game.rounds) > 1 else ''
			#listfile.write("\Auftrag{Gamename}{Gameid}{Victim}{Killer}{Signaturecode}{Spielende}{URL}\n")
			listfile.write(u"\\Auftrag{%s}{%s}{%s\\\\%s}{%s\\\\%s}{%s}{%s}{%s}{%s}\n" % 
				(
					utils.latexEsc(game.name), 
					utils.latexEsc(game.id), 
					r'\underline{\hskip4.5cm}', 
					r'\underline{\hskip4.5cm}', 
					r'\underline{\hskip2.5cm}', 
					r'\underline{\hskip2.5cm}', 
					r'\underline{\hskip2cm}', 
					utils.latexEsc(game.enddate.strftime("%d.%m.%Y %H:%M")), 
					utils.latexEsc(_url(req, 'view',  game.id)), 
					utils.latexEsc(roundname)
				) 
			)
	listfile.close()
	cwd = os.getcwd()
	os.chdir(tmptexdir)
	os.system("xelatex moerder.tex")
	os.chdir(cwd)
	shutil.copyfile(tmptexdir + "/moerder.pdf", os.path.join(g.savegamedir, "%s.pdf" % game.id))

@route('/pdfdownload', '/pdfdownload/<id>/<mastercode>/<publicid>')		
def pdfdownload(id, mastercode, publicid):
	game = _loadgame(id)
	filename = os.path.join(g.savegamedir, "%s_%s.pdf" % (game.id, publicid))
	if mastercode == game.mastercode:
		if not os.path.isfile(filename):
			return gameerror(req, u"Da gibt es kein passendes PDF")
		else:
			pdf = open(filename, 'r')
			ret = pdf.read()
			pdf.close()
			return _response(ret, 'application/pdf')
	else:
		return gameerror(req, u"Das war nicht der richtige Mastercode")

@route('/pdfget', '/pdfget/<id>/<mastercode>/<int:count>')
def pdfget(id, mastercode, count=0):
	game = _loadgame(id)
	filename = os.path.join(g.savegamedir, "%s.pdf" % game.id)
	if mastercode == game.mastercode:
		if not os.path.isfile(filename):
			if count == 0:
				filename = game.pdfgen()
			else:
				try:
					_pdfblankgen(req, int(count), game)
				except:
					return gameerror(req, u"Das war keine Zahl...")
		pdf = open(filename, 'r')
		ret = pdf.read()
		pdf.close()
		if not count == 0:
			os.unlink(filename)
		return _response(ret, 'application/pdf')
	else:
		return gameerror(req, u"Das war nicht der richtige Mastercode!")

@route('/htmlget', '/htmlget/<id>/<mastercode>')
def htmlget(id, mastercode):
	game = _loadgame(id)
	if mastercode == game.mastercode:
		#TODO req.content_type = 'text/xml;charset=utf-8'
		stream = render_template('auftrag.html', game = game)
		return stream
	else:
		return gameerror(req, u"Das war nicht der richtige Mastercode!")


# Funktion zur Generierung der Farbzuordnung für die Runden eines Spiels
def generate_colorlist(game):
    """
    Generiert ein Wörterbuch, das die Namen der Runden eines Spiels
    mit Farben im rgba()-Format verknüpft.

    :param game: Das Spielobjekt mit den Rundeninformationen
    :return: Ein Wörterbuch mit Runden-Namen als Schlüssel und Farben als Werte
    """
    colors = utils.colorgen(0.86, format='rgba()')
    colorlist = {}
    for round in game.rounds.values():
        colorlist[str(round.name)] = next(colors)
    return colorlist


@app.route('/')
def index():
	return redirect(url_for('start'))

@app.route('/start')
def start():
	return _mainstream('index.html')

@app.route('/newgameform')
def newgameform():
	return _mainstream('newgameform.html')

@app.route('/<id>',  methods=["GET", "POST"])
@route('/view', '/view/<id>')
def view(id, msg = ""):
    stream = None
    game = None
    try:
        game = _loadgame(id, False)
    except:
        stream = _mainstream('error.html', errormsg = "Sorry, Spiel-ID %s  existiert nicht." % id, returnurl="start")
    else:
        # Pass `p` explicitly to the template if needed
        p = game.players[0] if game.players else None  # Example logic
        colorlist = generate_colorlist(game)
        stream = _mainstream('view.html', game=game, errormsg=msg, p=p, colorlist=colorlist, utils=utils, max=max)
    return stream

@route('/wall', '/wall/<id>')
def wall(id, msg = "", ajax=0):
    stream = None
    games = []
    try:
        for gameid in id.split(':'):
            games.append(_loadgame(gameid, False))
    except:
        stream = _mainstream('error.html', errormsg = "Sorry, Spiel-ID %s  existiert nicht." % id, returnurl="start")
    else:
        if ajax == '1':
            selectors = [ "//*[@id='listplayers']" ]
            stream = _ajaxstream('wall.html', selectors, games = games, errormsg = None)
            return _response(stream, 'text/xml')
        else:
            stream = _mainstream('wall.html', games = games, errormsg = msg)

    return stream

@route('/error')
def gameerror(msg = "", returnurl = "index", gameid=None, mastercode=None, **kwargs):
	#game = _loadgame(id, False)
	stream = _mainstream('error.html', errormsg = msg, returnurl = returnurl)
	return stream


@route('/addplayer')
def addplayer(gameid, spielername, zusatzinfo, email='', email2='', subgame='', ajax=0):
    err = ''
    if email != email2:
        stream = _mainstream('error.html', errormsg = "Die beiden Mailadressen sind nicht gleich!", returnurl = 'view/%s' % gameid)
        return stream
    game = _loadgame(gameid)
    print(spielername)
    print(g.u8(spielername))
    try:
        if isinstance(game, moerderklassen.MultiGame):
            game.addPlayer(g.u8(spielername), g.u8(zusatzinfo), g.u8(email), g.u8(subgame) )
        else:
            game.addPlayer(g.u8(spielername), g.u8(zusatzinfo), g.u8(email) )
        gameid = _savegame(game)
    except GameError as e:
        err = e.__str__()
    else:
        err = "Neuer Mitspieler: %s" % g.u8(spielername)
    if ajax == '1':
        selectors = [ "//*[@id='listplayers']", "//*[@id='gameinfo']" ]
        stream = _ajaxstream('view.html', selectors, game = game, errormsg = err)
        return _response(stream, 'text/xml')
    else:
        return redirect(_url(req, 'view', gameid, err))


@route('/creategame')
def creategame(action, rundenname, kreiszahl, enddate, rundenid='', desc=None, name="", gamemastermail=None, createmultigame=False, createtestgame=False):
	if name != "":
		return gameerror(msg=u"I think you're a spammer. Oder dein Autofill hat ein verstecktes Feld zu viel ausgefüllt.")
	game = None
	if createtestgame:
		rundenid = 'test' + wordconstruct.WordGenerator().generate(6)
	if createmultigame:
		game = moerderklassen.MultiGame(
			G.u8(rundenname), 
			int(kreiszahl), 
			enddate, 
			_url(req, 'view',  rundenid), 
			rundenid,
			G.u8(desc)
		)
	else:
		game = moerderklassen.Game(
			G.u8(rundenname), 
			int(kreiszahl), 
			enddate, 
			_url(req, 'view',  rundenid), 
			rundenid,
			G.u8(desc)
		)
	game.url = _url(req, 'view', game.id)
	game.gamemastermail = gamemastermail
	g.fname = os.path.join(g.savegamedir, '%s.pkl' % game.id)
	print(game)
	if not os.path.exists(g.fname):
		g.lockfile = filelock.FileLock(g.fname + '.lock')
		try:
			gameid = _savegame(game, True)
		except Exception as e:
			return gameerror(msg=e.__str__())
	else:
		return gameerror(msg="Spiel %s existiert bereits!" % game.id)
	game.templatedir = g.templatedir
	game.sendgamemastermail()
	stream = _mainstream('creategame.html', gameid = game.id, url = _url(req, 'view', id=game.id), mastercode = game.mastercode, game = game)
	return stream


@route('/addtomultigame')
def addtomultigame(action, gameid, mastercode, subgamename="", subgameid='', desc=''):

	game = _loadgame(gameid)
	if action == 'addtomultigame':
		game.addGame(mastercode, subgameid, subgamename, desc)
		_savegame(game)

	stream = _mainstream('creategame.html', gameid = game.id, url = _url(req, 'view', id=game.id), mastercode = game.mastercode, game = game)
	return stream


@route('/startgame', '/startgame/<gameid>/<mastercode>')
def startgame(gameid, mastercode):
    game = _loadgame(gameid)
    try:
        game.start(mastercode)
    except GameError as e:
        return gameerror(req, _url(req, "view", id=gameid, errormsg=e.__str__()))
    gameid = _savegame(game)
    try:
        _pdfgen(game)
    except Exception as e:
        print(e)
        pass
    return redirect(_url(req, 'view', gameid))
    #stream = _mainstream('startgame.html', game = game, adminurl = _url(req, 'admin', game.id), viewurl = _url(req, 'view', id=game.id))
    #return stream.render('xhtml')


@route('/gamegraph', '/gamegraph/<id>/<roundid>/<mastercode>')
def gamegraph(id, roundid, mastercode=''):
	game = None
	tries = 0
	while tries < 10:
		try:
			game = _loadgame(id, False)
			tries = 10
		except:
			time.sleep(0.01)
			tries += 1
	round = game.rounds[roundid]
	adminview = (mastercode == game.mastercode or game.status == 'OVER')
	fname = os.path.join(g.savegamedir, '%s_%s%s.svg' % (game.id, round.name, '-admin' if adminview else ''))
	tries = 0
	while tries < 10:
		try:
			moerdergraph(round, fname, adminview)
			tries = 10
		except:
			time.sleep(0.01)
			tries += 1
	req.content_type = 'image/svg+xml'
	ret = None
	tries = 0
	while tries < 10:
		img = file(fname, 'r')
		try:
			ret = img.read()
			tries = 10
		except:
			time.sleep(0.01)
			tries += 1
		finally:
			img.close()
	return ret
	
@route('/gamegraphall', '/gamegraphall/<id>/<roundid>/<mastercode>')
def gamegraphall(id, roundid='', mastercode=''):
    game = None
    tries = 0
    while tries < 10:
        try:
            game = _loadgame(id, False)
            tries = 10
        except:
            time.sleep(0.01)
            tries += 1
    adminview = (mastercode == game.mastercode or game.status == 'OVER')
    fname = os.path.join(g.savegamedir, '%s_%s%s%s%s.svg' % (game.id, roundid, 'full', '-admin' if adminview else '', '-over' if game.status == 'OVER' else ''))
    tries = 0
    while tries < 10 and ( (game.status != 'OVER') or (game.status == 'OVER' and not os.path.isfile(fname)) ) :
        try:
            if len(roundid) < 1:
                moerdergraphall(game, fname, adminview)
            else:
                moerdergraphall(game, fname, adminview, rounds=game.rounds[roundid])
            tries = 10
        except:
            raise
            time.sleep(0.01)
            tries += 1
    ret = None
    tries = 0
    print(fname)
    while tries < 10:
        img = None
        try:
            print(fname)
            img = open(fname, 'r')
            ret = img.read()
            print(img)
            tries = 10
        except:
            time.sleep(0.01)
            tries += 1
        finally:
            if img is not None:
                img.close()
    print(ret)
    if not ret:
        return _response('<svg xmlns="http://www.w3.org/2000/svg"><text x="10" y="20" fill="red">Fehler: Kein Graph generiert.</text></svg>', 'image/svg+xml')
    return _response(ret, 'image/svg+xml')

@route('/admin',  methods=["GET", "POST"])
def admin(id=None, mastercode=None, action=None, round=None, killer=None, victim=None, datum=None, reason=None, ajax=0, spielername=None, zusatzinfo=None, email=''):
    stream = None
    if id is not None:
        err = ''
        selectors = [ "//*[@id='listplayers']", "//*[@id='gameinfo']" ]
        game = _loadgame(id)
        if mastercode == game.mastercode:
            if victim == 'ERROR':
                err = u'Du solltest schon ein Opfer aus der Liste auswählen!'
                selectors = "//*[@id='makeakill']"
            elif action == 'removeplayer':
                playername = game.findPlayerByPublicID(victim).name
                try:
                    game.removePlayer(victim)
                except GameError as e:
                    err = u'Fehler: %s' % e.__str__()
                else:
                    err = u'%s wurde aus dem Spiel entfernt.' % playername
            elif action == 'addplayer':
                try:
                    game.addPlayer(G.u8(spielername), G.u8(zusatzinfo), G.u8(email))
                except GameError as e:
                    err = e.__str__()
                else:
                    err = "Neuer Mitspieler: %s" % G.u8(spielername)
            elif action == 'killplayer':
                participant = game.rounds[round].getParticipant(victim)
                if len(killer) < 1:
                    killer = None
                try:
                    game.kill(killer, participant.id, datum, G.u8(reason))
                except GameError as e:
                    err = u'Fehler: %s' % e.__str__()
                else:
                    err = u'Eingetragen: %s wurde erlegt.' % participant.player.name
                    selectors.append( "//*[@id='makeakill']" )
            elif action == 'kickplayer':
                playername = game.findPlayerByPublicID(victim).name
                try:
                    game.kickPlayer(victim, mastercode)
                except GameError as e:
                    err = u'Fehler: %s' % e.__str__()
                else:
                    err = u'%s wurde aus dem Spiel entfernt.' % playername
            elif action == 'revertkill':
                try:
                    game.revertkill(victim)
                except GameError as e:
                    err = e.__str__()
                else:
                    err = u'Mord an %s wurde zurückgenommen' % game.findParticipant(victim).player.name
            elif action == 'editkill':
                err = u'Not implemented yet. Muss momentan noch durch "undo" und neu eintragen durchgeführt werden.'
            else:
                err = u'No valid action'
            id = _savegame(game)

            if ajax == '1':
                logging.debug(selectors)
                sorted_players = sorted(game.players, key=lambda p: (p.name or '') + (p.info or ''))
                
                stream = _mainstream('admin.html', game=game, errormsg=err, sorted_players=sorted_players, sorted=sorted,utils=utils,len=len)
            else:
                sorted_players = sorted(game.players, key=lambda p: (p.name or '') + (p.info or ''))
                stream = _mainstream('admin.html', game = game, errormsg = err, sorted_players=sorted_players,sorted=sorted,utils=utils,len=len)
        else:
            err = u'Das war nicht der Game Master Code zu diesem Spiel!'
        if stream is None:
            if ajax == '1':
                stream = _ajaxstream('view.html', selectors, game = game, errormsg = err)
            else:
                stream = _mainstream('view.html', game = game, errormsg = err)
    else: #if id is None
        stream = _mainstream('index.html', errormsg = "")
    if ajax == '1':
        return _response(stream, 'text/xml')
    else:
        return stream


@route('/killplayer')
def killplayer(gameid, victimid, killerpublicid, datum, reason, ajax=0):
	errormsg = ''
	game = _loadgame(gameid)
	try:
		game.kill(killerpublicid, victimid, datum, G.u8(reason))
		errormsg = u'Spieler wurde erlegt'
	except GameError as e:
		errormsg = e.__str__()
	gameid = _savegame(game)
	selectors = "//*[@id='inner-content']"
	if ajax == '1':
		stream = _ajaxstream('view.html', selectors, game = game, errormsg = errormsg)
		return _response(stream, 'text/xml')
	else:
		stream = _mainstream('view.html', game = game, errormsg = errormsg)
		return stream



@route('/redir', '/redir/<gameid>')
def redir(gameid):
	redirect(_url(req, 'view', gameid))

if __name__ == '__main__':
	app.run(host='0.0.0.0', debug=True)
