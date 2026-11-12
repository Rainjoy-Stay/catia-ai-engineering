"""Actual face adjacency graph; support groups never merge disconnected faces."""


def build_face_route_graph(records):
    bodies=[]
    for record in records:
        nodes={}; edges=set()
        for seed in record['seeds']:
            if seed.get('topology_verified') is not True: continue
            torus=seed['torus_face_id']
            for cylinder in seed.get('shared_edge_cylinder_face_ids',[]):
                if cylinder not in seed['cylinder_face_ids']: continue
                nodes[cylinder]={'face_id':cylinder,'surface_type':'CYLINDER'}
                nodes[torus]={'face_id':torus,'surface_type':'TORUS'}
                edges.add(tuple(sorted((cylinder,torus))))
        adjacency={n:set() for n in nodes}
        for a,b in edges: adjacency[a].add(b); adjacency[b].add(a)
        remaining=set(nodes); components=[]
        while remaining:
            start=min(remaining); seen={start}; stack=[start]
            while stack:
                current=stack.pop()
                for neighbour in adjacency[current]-seen:
                    seen.add(neighbour); stack.append(neighbour)
            remaining-=seen
            component_edges=[list(e) for e in sorted(edges) if e[0] in seen]
            branch=[n for n in sorted(seen) if len(adjacency[n])>2]
            cycle_rank=len(component_edges)-len(seen)+1
            components.append({'face_ids':sorted(seen),'edges':component_edges,
                'branch_faces':branch,'leaf_faces':[n for n in sorted(seen) if len(adjacency[n])==1],
                'cycle_rank':cycle_rank,'classification':
                'BRANCHED_FACE_GRAPH' if branch else 'CYCLIC_FACE_GRAPH' if cycle_rank else 'CHAIN_FACE_GRAPH',
                'status':'NOT_EVALUATED','centerline_reconstructed':False,
                'engineering_pipe_confirmed':False})
        bodies.append({'source_body_index':record['source_body_index'],
            'nodes':[nodes[n] for n in sorted(nodes)],'edges':[list(e) for e in sorted(edges)],
            'components':components,'status':'NOT_EVALUATED'})
    return {'bodies':bodies,'scope':'VERIFIED_SHARED_EDGES_BETWEEN_CYLINDER_AND_TORUS_FACES_ONLY',
            'limits':'Face graph chains or cycles are not physical tube routes; omitted plane and other faces can alter connectivity'}
