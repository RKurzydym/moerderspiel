#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os.path
from graphviz import Digraph
import textwrap
import math
import colorsys
import pickle
from moerderklassen import *
from utils import colorgen
import utils




def moerdergraphall(game, filename, alledges=False, nodefontsize=8.0, edgefontsize=8.0, rounds=None):
	if rounds is None:
		rounds = list(game.rounds.values())
	elif type(rounds) is not list:
		rounds = [rounds]

	G = Digraph("Moerder", format="png")
	G.attr(model='subset', overlap='compress', splines='true', packmode='graph', rankdir='LR')

	nodes = {}
	prev_node = first_node = node = None
	participants = sorted(rounds, key=lambda x: len(x.participants))[-1].participants[:]

	# Game Master node
	G.node('Game Master', label='Game Master', fontsize=str(nodefontsize), fontname='arial', color='gray', fontcolor='gray', style='rounded')
	# Invisible node for layout
	G.node('invisible', style='invisible', pos='0,0!')

	if len(participants) > 120:
		print("hi")	
		G.node('sorry', label='Sorry, zu viele Nodes in diesem Graph...', style='rounded,filled', fontsize=str(nodefontsize), penwidth='2', color='#00003380', fillcolor='#FFFFFF00', margin='0.01')
		G.render(filename, view=False)
		return
	if len(participants) > 120:
		print("hi")
		sorrynode = G.add_node(u'Sorry, zu viele Nodes in diesem Graph...')
		sorrynode.label = u'Sorry, zu viele Nodes in diesem Graph...'
		sorrynode.style = 'rounded,filled'
		sorrynode.fontsize = nodefontsize
		sorrynode.style = 'rounded,filled'
		sorrynode.penwidth = 2
		sorrynode.color = '#00003380'
		sorrynode.fillcolor = '#FFFFFF00'
		sorrynode.margin = 0.01
		# do the layout math and save to file
		if graph.__dict__.has_key('_yapgvb_py'):
			# if yapgvb works in python-only mode
			rc = MyRenderingContext()
			G.layout(graph.engines.dot, rendering_context=rc)
			G.render(filename, rendering_context=rc)
		else:
			# if yapgvb has libboost support compiled in
			G.layout(graph.engines.dot)
			G.render(filename)
		return
	massmurderers = game.getMassMurderer()
	massmurdererlist = [ player.public_id for player in massmurderers['killers'] ] if len(massmurderers) > 0 else []

	if not alledges:
		participants.sort(key = lambda p: p.player.name + p.player.info)
	nodecount = len(participants)
	nodesperline = max(1, math.trunc(math.sqrt(nodecount)))
	nodenumber = 0
	for participant in participants:
		nodenumber += 1
		name = participant.player.name
		if len(participant.player.info) > 0:
			name += "\n" + participant.player.info
		name = utils.dotescape(name)
		pid = participant.player.public_id
		# Default node attributes
		attrs = {
			'label': name,
			'fontsize': str(nodefontsize),
			'fontname': 'arial',
			'color': '#00003380',
			'fillcolor': '#FFFFFF00',
			'penwidth': '2',
			'margin': '0.01',
			'style': 'rounded,filled',
		}
		nodeweight = game.getDeathsCount(participant) + game.getKillsCount(participant)
		# Kicked participants are gray/dashed
		if participant.killed() and participant.killedby.killer is None:
			attrs['style'] += ',dashed'
		# Mass murderers are black
		if pid in massmurdererlist:
			attrs['color'] = 'black'
			attrs['fillcolor'] = 'black'
			attrs['fontcolor'] = 'white'
		# Dead participants are red
		if (game.getDeathsCount(participant) >= len(game.rounds)):
			attrs['color'] = '#FF0000FF'
			attrs['penwidth'] = '2'
		# Add node
		G.node(pid, **attrs)
		nodes[pid] = pid
		#print(f"player id: {pid}")
		# Invisible edge for nodeweight==0
		if nodeweight == 0:
			G.edge('invisible', pid, style='invisible', arrowhead='none', weight='0.1')


	colorgenerator = colorgen(0.86)
	for round in game.rounds.values():
		edgecolor = next(colorgenerator)
		if round not in rounds:
			continue
		for participant in round.participants:
			if alledges or participant.killed():
				killer_id = participant.getInitialKiller().player.public_id
				victim_id = participant.player.public_id
				if killer_id not in nodes:
					print(f"Warnung: Initial-Killer {killer_id} nicht im Graph (z.B. für Opfer {victim_id})")
					continue
				if victim_id not in nodes:
					print(f"victim id not found {victim_id}")
					continue
				G.edge(
					nodes[killer_id],
					nodes[victim_id],
					color=edgecolor,
					style='dashed',
					penwidth='2',
					weight='6.0'
				)
			if participant.killed():
				if not participant.killedby.killer is None:
					from_id = nodes[participant.killedby.killer.player.public_id]
				else:
					from_id = 'Game Master'
				label = utils.dateformat(participant.killedby.date) + ":\n"
				maxlinelen = max(24, math.trunc(math.ceil(math.sqrt(6 * len(participant.killedby.reason)))))
				label += "\n".join(textwrap.wrap(participant.killedby.reason, maxlinelen)).replace('"', "'")
				label = ''.join([ c for c in label if ord(c) < 2048])
				G.edge(
					from_id,
					nodes[participant.player.public_id],
					color=edgecolor,
					fontcolor='red',
					style='solid',
					penwidth='4',
					weight='10.0',
					label=label,
					fontsize=str(edgefontsize),
					fontname='arial'
				)
	# Graphviz render
	print(filename)
	G.render(filename[:-4], view=False, format='svg')


def _loadgame(gamefile):
	input = open(gamefile, 'rd')
	ret = pickle.load(input)
	input.close()
	return ret

if __name__ == "__main__":
	import sys
	game = _loadgame(sys.argv[1])
	moerdergraphall(game, sys.argv[2], alledges=True)
	
