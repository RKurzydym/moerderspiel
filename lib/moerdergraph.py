#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os.path
from graphviz import Digraph
import textwrap
import math
import utils
from moerderklassen import *

def u8(s):
	try:
		return s.decode('utf8')
	except UnicodeDecodeErrors:
		try:
			return s.decode('latin1')
		except UnicodeDecodeError:
			return None

def moerdergraph(round, filename, alledges=False, nodefontsize=8.0, edgefontsize=8.0):
	G = Digraph("Moerder", format="png")
	nodes = {}
	participants = round.participants[:]
	if not alledges:
		participants.sort(key = lambda p: p.player.name + p.player.info)
	for participant in participants:
		name = participant.player.name
		if len(participant.player.info) > 0:
			name += "\n" + participant.player.info
		pid = participant.player.public_id
		attrs = {
			'label': name,
			'fontsize': str(nodefontsize),
			'fontname': 'arial',
			'margin': '0.03',
		}
		if participant.killed() and participant.killedby.killer is None:
			attrs['color'] = 'gray'
			attrs['fontcolor'] = 'gray'
		if participant.killed() and not participant.killedby.killer is None:
			attrs['color'] = 'red'
			attrs['fontcolor'] = 'red'
		G.node(pid, **attrs)
		nodes[pid] = pid

	for participant in round.participants:
		if alledges or participant.killed():
			G.edge(
				nodes[participant.getInitialKiller().player.public_id],
				nodes[participant.player.public_id],
				color='black',
				weight='1.0'
			)
		if participant.killed():
			if not participant.killedby.killer is None:
				from_id = nodes[participant.killedby.killer.player.public_id]
			else:
				# special case of a game master kill
				G.node('vorzeitig ausgestiegen', fontsize=str(nodefontsize), fontname='arial', color='gray', fontcolor='gray')
				from_id = 'vorzeitig ausgestiegen'
			label = utils.dateformat(participant.killedby.date) + ":\n"
			maxlinelen = max(24, math.trunc(math.ceil(math.sqrt(6 * len(participant.killedby.reason)))))
			label += "\n".join(textwrap.wrap(participant.killedby.reason, maxlinelen))
			G.edge(
				from_id,
				nodes[participant.player.public_id],
				color='red',
				fontcolor='red',
				weight='1.0',
				label=label,
				fontsize=str(edgefontsize),
				fontname='arial'
			)
	# Graphviz render
	G.render(filename, view=False)
