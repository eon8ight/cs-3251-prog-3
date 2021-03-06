#!/usr/bin/python3
"""
This file runs the simulation.
"""
import math, re, sys

from event import Event, EventQueue
from graph import Graph, Edge
from router import RoutingTable

BASIC                        = 0
SPLIT_HORIZON                = 1
SPLIT_HORIZON_POISON_REVERSE = 2
"""
This turns a file into an undirected graph representation of the network
"""
def file_to_undirected_graph( filename ):
    global num_routers, updates

    handle      = open( filename, 'r' )
    num_routers = int( handle.readline() )

    topology = Graph()

    for line in handle:
        match   = re.match( r'(\d+)\s+(\d+)\s+(\d+)', line )
        router1 = int( match.group( 1 ) )
        router2 = int( match.group( 2 ) )
        cost    = int( match.group( 3 ) )

        edge = Edge( router1, router2, cost )

        if not topology.containsVertex( router1 ):
            topology.addVertex( router1, RoutingTable( num_routers, router1 ) )

        if not topology.containsVertex( router2 ):
            topology.addVertex( router2, RoutingTable( num_routers, router2 ) )

        topology.addEdge( edge )
        updates[router1] = True
        updates[router2] = True

    return topology

"""
This turns a file into an event queue.
"""
def file_to_topological_events( filename ):
    handle = open( filename, 'r' )

    event_queue = EventQueue()

    for line in handle:
        match     = re.match( r'(\d+)\s+(\d+)\s+(\d+)\s+(-?\d+)', line )
        round_num = int( match.group( 1 ) )
        router1   = int( match.group( 2 ) )
        router2   = int( match.group( 3 ) )
        cost      = int( match.group( 4 ) )

        to_add = Event( round_num, router1, router2, cost )
        event_queue.addEvent( to_add )

    event_queue.prepare()
    return event_queue

"""
Usage definition
"""
def usage():
    print( 'Usage: ./simulator.py <topology file> <event file> <verbose value>' )
    exit( 0 )

"""
Translates network into a table representation for printing.
"""
def tableize( network, on_round_0=False ):
    global num_routers

    ret_table = [ [ None for i in range( num_routers ) ] for j in range( num_routers ) ]

    for router in range( 0, num_routers ):
        routing_table = network.vertices[router + 1]

        for i in range( 0, len( routing_table.coordinates ) ):
            if i == router:
                next_hop  = i + 1
                cost      = 0
                hop_count = 0
            elif routing_table.coordinates[i] is None:
                next_hop  = -1
                cost      = -1
                hop_count = -1
            else:
                x, y      = routing_table.coordinates[i]
                next_hop  = routing_table.hops[i]
                cost      = routing_table.table[x - 1][y - 1]
                hop_count = routing_table.numHops[x - 1][y - 1]

            ret_table[router][i] = ( next_hop, cost, hop_count )

    return ret_table

"""
Returns if the table has reached a count-to-infinity problem, based on hop count
"""
def is_count_to_infinity( table ):
    for i in table:
        for j in i:
            if j[2] >= 100:
                return True

    return False

"""
This prints out the internal representation of each router (for debugging)
"""
def print_network( network ):
    for vertex in network.vertices:
        print( 'Router ' + str( vertex ) + ':' )
        print( str( network.vertices[vertex] ) )
        print( str( network.vertices[vertex].coordinates ) )
        print( '\n' )

"""
Prints a pretty representation of a given table.
"""
def pretty_print( table ):
    global num_routers

    retval = ''

    s = [ [ '{},{}'.format( e[0], e[2] ) for e in row ] for row in table ]
    # s.insert( 0, [ str( i ) for i in range( 1, num_routers + 1 ) ] )

    lens  = [ max( map( len, col ) ) for col in zip( *s ) ]
    fmt   = '    '.join( '{{:{}}}'.format( x ) for x in lens )
    table = [ fmt.format( *row ) for row in s ]

    for i in range( 0, len( table ) ):
        retval += '{}  '.format( i + 1 ) + table[i] + '\n'

    return retval

"""
Sets up the network with initial costs to neighboring nodes for each router.
"""
def setup_network( network, verbose ):
    for vertex in network.vertices:
        vertexNeighbors = network.getNeighbors( vertex )

        for x in vertexNeighbors.keys():
            network.vertices[vertex].setCost( x, x, vertexNeighbors[x] )
            network.vertices[vertex].setCoordinate(x, x)
            network.vertices[vertex].setHop( x, x )
            network.vertices[vertex].setNumHops( x, x, 1 )

"""
Basic DVR algorithm
"""
def iter_basic( network ):
    global updates

    changed = False
    cloned  = {}

    #go through all nodes in the graph
    for vertex in network.vertices:

        #clone the node for sending
        cloned[vertex] = network.vertices[vertex].clone()

    #go through all nodes in the graph
    for vertex in network.vertices:

        #if it had no updates, it sends nothing
        if not updates[vertex]:
            continue

        #get the currents node's neighbors
        vertex_neighbors = network.getNeighbors( vertex )

        #go through the neighbor list
        for neighbor in vertex_neighbors.keys():

            #go through all table entries
            for to in range( 0, len( network.vertices[vertex].table ) ):
                to_router = to + 1

                #skip ourselves
                if to_router == vertex:
                    continue

                #send the current entry in the DV to the neighbor we are currently on, neighbor updates
                if network.vertices[vertex].coordinates[to_router - 1] is not None:
                    via = network.vertices[vertex].coordinates[to_router - 1][1]
                    existing_cost = cloned[vertex].getCost( to_router, via )

                    #if it has existing cost we need to set
                    if existing_cost is not None:

                        #calculate our newcost
                        new_cost  = existing_cost + network.vertices[neighbor].getCost( vertex, vertex )

                        #this will tell us if we changed anything in the neighbor
                        didChange = network.vertices[neighbor].setCost( to_router, vertex, new_cost )

                        #if we did change things, we need to set the update flags and numHops
                        if didChange:
                            hop_count = 1 + cloned[vertex].getNumHops( to_router, via )
                            network.vertices[neighbor].setNumHops( to_router, vertex, hop_count )
                            updates[neighbor] = True

                        #here we can set if anything changed at all during the sending
                        if not changed and didChange:
                            changed = True

    return changed

"""
Split Horizon DVR algorithm
"""
def iter_split_horizon( network ):
    global updates

    changed = False
    cloned  = {}

    #go through all of the nodes in the network
    for vertex in network.vertices:
        #make a clone of it for sending
        cloned[vertex] = network.vertices[vertex].clone()

    #go through all of the nodes in the network
    for vertex in network.vertices:

        #if it has no updates, it does not send
        if not updates[vertex]:
            continue

        #get all of this nodes neighbors
        vertex_neighbors = network.getNeighbors( vertex )

        #go through all of the neighbors
        for neighbor in vertex_neighbors.keys():

            #got through entries in the routing table
            for to in range( 0, len( network.vertices[vertex].table ) ):
                to_router = to + 1

                #skip ourselves
                if to_router == vertex:
                    continue

                #go through our least costs in DV
                if network.vertices[vertex].coordinates[to_router - 1] is not None:

                    #calculate existing cost (on enighbor's side)
                    via = network.vertices[vertex].coordinates[to_router - 1][1]
                    existing_cost = cloned[vertex].getCost( to_router, via )

                    #if this cost is not None, we should update
                    if existing_cost is not None:

                        #calcualte additional cost to go this path
                        additional_cost = network.vertices[neighbor].getCost( vertex, vertex )

                        #if we are reporting a path where the next hop is the neighbor we are reporting to, we will skip this
                        if network.vertices[vertex].hops[to] != neighbor:

                            #calculate new costs, see if it changes from setCost
                            new_cost  = existing_cost + additional_cost
                            didChange = network.vertices[neighbor].setCost( to_router, vertex, new_cost )

                            #if we changed we need to set hop count and updates
                            if didChange:
                                hop_count = 1 + cloned[vertex].getNumHops( to_router, via )
                                network.vertices[neighbor].setNumHops( to_router, vertex, hop_count )
                                updates[neighbor] = True

                            #need to say if something has changed in this send block
                            if not changed and didChange:
                                changed = True

    return changed

"""
Split Horizon with Posion Reverse DVR algorithm
"""
def iter_split_horizon_poison_reverse( network ):
    global updates

    changed = False
    cloned  = {}

    #go through all nodes in the network, clone them for sending
    for vertex in network.vertices:
        cloned[vertex] = network.vertices[vertex].clone()

    #go through all nodes in the network
    for vertex in network.vertices:

        #if it does not have updates, we will skip it
        if not updates[vertex]:
            continue

        #get this node's neighbors
        vertex_neighbors = network.getNeighbors( vertex )

        #go through all of the neighbors to send DV
        for neighbor in vertex_neighbors.keys():

            #go through our routing table
            for to in range( 0, len( network.vertices[vertex].table ) ):
                to_router = to + 1

                #skip ourselves
                if to_router == vertex:
                    continue

                #if we have a DV entry for this path, go in here
                if network.vertices[vertex].coordinates[to_router - 1] is not None:

                    #calculate the noe we go through and the existing cost
                    via = network.vertices[vertex].coordinates[to_router - 1][1]
                    existing_cost = cloned[vertex].getCost( to_router, via )

                    #if the existing cost exists, go in here
                    if existing_cost is not None:

                        #calculate additional cost
                        additional_cost = network.vertices[neighbor].getCost( vertex, vertex )

                        #if the path we are sending to a neighbor has that enighbor as its next hop, we set the cost to be inifinte
                        if network.vertices[vertex].hops[to] != neighbor:
                            new_cost  = existing_cost + additional_cost
                        else:
                            new_cost = math.inf

                        #call setCost
                        didChange = network.vertices[neighbor].setCost( to_router, vertex, new_cost )

                        #if we changed things, we need to update hop count and the updates list
                        if didChange:
                            hop_count = 1 + cloned[vertex].getNumHops( to_router, via )
                            network.vertices[neighbor].setNumHops( to_router, vertex, hop_count )
                            updates[neighbor] = True

                        #record if we changed anything this round on this send
                        if not changed and didChange:
                            changed =  True

    return changed

"""
Updates the network based on events.
"""
def update_network( network, events ):
    global num_routers, updates

    #updates the graph representation of the network
    network.updateGraph( events )

    #go through th events
    for e in events:
        r1   = e.router1
        r2   = e.router2
        cost = e.cost

        #negative number means a removed edge
        if cost < 0:
            cost = None

        #this will remove and edge of from the graph and update the affected parties' routing tables
        #else we will set the edge costs to the new one and also update affected parties' routing tables
        if cost is None:
            for i in range( 1, num_routers + 1 ):
                # print( '{}: to {} via {} -> {}'.format( r1, i, r2, cost ) )
                network.vertices[r1].setCostFromEvent( i, r2, None )
                # print( '{}: to {} via {} -> {}'.format( r2, i, r1, cost ) )
                network.vertices[r2].setCostFromEvent( i, r1, None )
                network.vertices[r1].setNumHops( i, r2, -1 )
                network.vertices[r2].setNumHops( i, r1, -1 )
        else:
            network.vertices[r1].setCostFromEvent( r2, r2, cost )
            network.vertices[r2].setCostFromEvent( r1, r1, cost )
            network.vertices[r1].setNumHops( r2, r2, 1 )
            network.vertices[r2].setNumHops( r1, r1, 1 )

        #have to set updates to true
        updates[r1] = True
        updates[r2] = True

        #get neighbors
        r1_neighbors = network.getNeighbors( r1 )
        r2_neighbors = network.getNeighbors( r2 )

        #must fix the neighbors a bit
        for neighbor in r1_neighbors.keys():
            if neighbor == r2:
                continue

            neighbor_r2_cost = network.getEdgeCost( neighbor, r2 )
            neighbor_r1_cost = network.getEdgeCost( neighbor, r1 )

            if neighbor_r2_cost is not None:
                new_cost = cost + neighbor_r2_cost if cost is not None else None
                # print( '{}: to {} via {} -> {}'.format( neighbor, r1, r2, new_cost ) )
                network.vertices[neighbor].setCostFromEvent( r1, r2, new_cost )
                updates[neighbor] = True

            if neighbor_r1_cost is not None:
                new_cost = cost + neighbor_r1_cost if cost is not None else None
                # print( '{}: to {} via {} -> {}'.format( neighbor, r2, r1, new_cost ) )
                network.vertices[neighbor].setCostFromEvent( r2, r1, new_cost )
                updates[neighbor] = True

        #must fix the neigbors a bit
        for neighbor in r2_neighbors.keys():
            if neighbor == r1:
                continue

            neighbor_r2_cost = network.getEdgeCost( neighbor, r2 )
            neighbor_r1_cost = network.getEdgeCost( neighbor, r1 )

            if neighbor_r2_cost is not None:
                new_cost = cost + neighbor_r2_cost if cost is not None else None
                # print( '{}: to {} via {} -> {}'.format( neighbor, r1, r2, new_cost ) )
                network.vertices[neighbor].setCostFromEvent( r1, r2, new_cost )
                updates[neighbor] = True

            if neighbor_r1_cost is not None:
                new_cost = cost + neighbor_r1_cost if cost is not None else None
                # print( '{}: to {} via {} -> {}'.format( neighbor, r2, r1, new_cost ) )
                network.vertices[neighbor].setCostFromEvent( r2, r1, new_cost )
                updates[neighbor] = True

"""
Runs a round of the current passed algorithm, and writes to file
"""
def dv_run( network, events, verbose, algoType ):
    global updates

    changed         = True
    round_num       = 2
    last_event_time = 0

    setup_network( network, verbose )

    str_buf = ''

    #verbose prints
    if verbose:
        str_buf += 'Round 1\n'
        table = tableize( network, True )
        str_buf += pretty_print( table )

    #main loop
    while True:
        round_events = events.getEvents( round_num )

        #perform updates from events this round
        if len( round_events ) > 0:
            update_network( network, round_events )
            last_event_time = round_num

        #run currrent algo
        if algoType == BASIC:
            changed = iter_basic( network )
        elif algoType == SPLIT_HORIZON:
            changed = iter_split_horizon( network )
        elif algoType == SPLIT_HORIZON_POISON_REVERSE:
            changed = iter_split_horizon_poison_reverse( network )

        #set updates (this is a failsafe)
        for vertex in network.vertices:
            updates[vertex] = network.vertices[vertex].updateCoordinates()

        #we're done
        if not changed and not events.hasEvents():
            break

        table = tableize( network )

        #verbose additions
        if verbose:
            str_buf += 'Round {}\n'.format( round_num )
            str_buf += pretty_print( table )
            #print( '\n' )
            #print_network( network )

        #chekc count to inifinity, output if so
        if is_count_to_infinity( table ):
            sys.exit( 'Encountered a count-to-infinity instability.' )

        round_num += 1

    #non verbose output
    if not verbose:
        table = tableize( network )
        str_buf += pretty_print( table )

    final_convergence_delay = round_num - 1 - last_event_time

    #convergence delay output
    str_buf += '\nConvergence Delay: {} round{}'.format( final_convergence_delay, 's' if final_convergence_delay != 1 else '' )
    # print( str_buf )

    outfile_name = 'output-'

    if algoType == BASIC:
        outfile_name += 'basic'
    elif algoType == SPLIT_HORIZON:
        outfile_name += 'split-horizon'
    elif algoType == SPLIT_HORIZON_POISON_REVERSE:
        outfile_name += 'split-horizon-with-poison-reverse'

    if verbose:
        outfile_name += '-detailed'

    outfile_name += '.txt'

    #write file
    outfile = open( outfile_name, 'w' )
    outfile.write( str_buf )
    outfile.close

"""
Main function, runs on command line call.
"""
def main( argv ):
    global updates

    if len( argv ) != 3:
        usage()

    topology_filename           = argv[0]
    topological_events_filename = argv[1]
    verbose                     = int( argv[2] ) == 1

    updates = {}

    #runs the basic DVR algorithm
    topology           = file_to_undirected_graph( topology_filename )
    topological_events = file_to_topological_events( topological_events_filename )
    dv_run( topology, topological_events, verbose, BASIC )

    #runs the split-horizon DVR algorithm
    topology           = file_to_undirected_graph( topology_filename )
    topological_events = file_to_topological_events( topological_events_filename )
    dv_run( topology, topological_events, verbose, SPLIT_HORIZON )

    #runs the split-horizon with posion reverse DVR algorithm
    topology           = file_to_undirected_graph( topology_filename )
    topological_events = file_to_topological_events( topological_events_filename )
    dv_run( topology, topological_events, verbose, SPLIT_HORIZON_POISON_REVERSE )

if __name__ == "__main__":
    main( sys.argv[1:] )

sys.exit( 0 )
