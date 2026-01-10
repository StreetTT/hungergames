from flask import Blueprint, render_template

root = Blueprint('root', __name__)

@root.route('/')
def index():
    return render_template('index.html')

@root.route('/game/<game_id>')
def view_game(game_id):
    return render_template('game.html', game_id=game_id)

@root.route('/stats/<game_id>')
def view_stats(game_id):
    return render_template('stats.html', game_id=game_id)