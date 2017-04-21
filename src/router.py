import math
from copy import deepcopy

class RoutingTable:
    def __init__( self, numRouters, router ):
        self.table       = [ [ None for i in range( numRouters ) ] for j in range( numRouters ) ]
        self.numHops     = [ [ 0 for i in range( numRouters ) ] for j in range( numRouters ) ]
        self.coordinates = [ None for i in range( numRouters ) ]
        self.router      = router
        self.hops        = [ None for i in range( numRouters ) ]

    def setNumHops( self, to, via, hops ):
        self.numHops[to - 1][via - 1] = hops

    def getNumHops( self, to, via ):
        return self.numHops[to - 1][via - 1]

    def getCost( self, to, via ):
        return self.table[to - 1][via - 1]

    def setCostFromEvent( self, to, via, cost ):
        self.table[to - 1][via - 1] = cost

    def setCost( self, to, via, cost ):
        #print ('From vertex {} telling {} about path to vertex {} with cost: {}'.format(via, self.router, to, cost) )
        if to == self.router or via == self.router:
            return False

        if    self.table[to - 1][via - 1] is None \
           or self.table[to - 1][via - 1] >= cost \
           or self.coordinates[to - 1] == ( to, via ):
            self.table[to - 1][via - 1] = cost
            return True

        return False

    def setHop( self, to, via ):
        if to == self.router or via == self.router:
            self.hops[to-1] = via
        elif to == via:
            self.hops[to-1] = via
        else:
            self.hops[to-1] = via

    def setCoordinate(self, index1, index2):
        self.coordinates[index1 - 1] = (index1, index2)

    def updateCoordinates( self ):
        ret = False

        for c in range( 0, len( self.table ) ):
            if not any( self.table[c] ):
                self.coordinates[c] = None
                self.hops[c]        = 0
                continue

            col = self.table[c].index( min( x for x in self.table[c] if x is not None ) )
            self.setHop( c + 1, col + 1 )

            if self.coordinates[c] != (c + 1, col + 1):
                self.coordinates[c] = (c + 1, col + 1)
                ret = True

        return ret

    def clone( self ):
        return deepcopy( self )

    def __str__( self ):
        tableStr = ''

        for i in range( 0, len( self.table ) ):
            for j in range( 0, len( self.table[i] ) ):
                if self.table[i][j] is None:
                    tableStr += 'X, '
                else:
                    tableStr += str( self.table[i][j] ) + ', '

            tableStr = tableStr.strip( ', ' )
            tableStr += '\n'

        tableStr  = tableStr.strip( ', \n' )
        tableStr += ''

        return tableStr
