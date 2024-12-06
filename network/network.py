import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
from ast import literal_eval

def create_fragrance_network(csv_path):
    # Load data
    df = pd.read_csv(csv_path)
    
    # Create network
    G = nx.Graph()
    
    # Add fragrance nodes
    for _, row in df.iterrows():
        G.add_node(row['perfume'], type='fragrance', brand=row['brand'])
        
        # Add accord edges
        accords = [a.strip().strip("'") for a in row['accords'].strip('[]').split(',')]
        for accord in accords:
            G.add_node(accord, type='accord')
            G.add_edge(row['perfume'], accord, type='has_accord')
            
        # Add note edges
        notes = [n.strip().strip("'") for n in row['notes'].strip('[]').split(',')]
        for note in notes:
            G.add_node(note, type='note')
            G.add_edge(row['perfume'], note, type='has_note')
    
    return G

def analyze_network(G):
    # Basic metrics
    print(f"Network Stats:")
    print(f"Nodes: {G.number_of_nodes()}")
    print(f"Edges: {G.number_of_edges()}")
    
    # Most common notes/accords
    note_nodes = [n for n, d in G.nodes(data=True) if d.get('type') == 'note']
    accord_nodes = [n for n, d in G.nodes(data=True) if d.get('type') == 'accord']
    
    print("\nMost Connected Notes:")
    note_degrees = sorted([(n, G.degree(n)) for n in note_nodes], key=lambda x: x[1], reverse=True)[:5]
    for note, degree in note_degrees:
        print(f"{note}: {degree} connections")
        
    print("\nMost Connected Accords:")
    accord_degrees = sorted([(a, G.degree(a)) for a in accord_nodes], key=lambda x: x[1], reverse=True)[:5]
    for accord, degree in accord_degrees:
        print(f"{accord}: {degree} connections")
    
    # Find communities
    communities = list(nx.community.greedy_modularity_communities(G))
    print(f"\nFound {len(communities)} distinct fragrance communities")
    
    return communities

def visualize_network(G, communities=None):
    pos = nx.spring_layout(G)
    
    plt.figure(figsize=(15, 15))
    
    # Draw nodes by type
    fragrances = [n for n, d in G.nodes(data=True) if d.get('type') == 'fragrance']
    notes = [n for n, d in G.nodes(data=True) if d.get('type') == 'note']
    accords = [n for n, d in G.nodes(data=True) if d.get('type') == 'accord']
    
    nx.draw_networkx_nodes(G, pos, nodelist=fragrances, node_color='lightblue', node_size=100)
    nx.draw_networkx_nodes(G, pos, nodelist=notes, node_color='lightgreen', node_size=50)
    nx.draw_networkx_nodes(G, pos, nodelist=accords, node_color='pink', node_size=75)
    
    nx.draw_networkx_edges(G, pos, alpha=0.2)
    plt.title("Fragrance Network: Blue=Fragrances, Green=Notes, Pink=Accords")
    plt.show()

if __name__ == "__main__":
    # Create and analyze network
    G = create_fragrance_network("raw_data/top_100_mens_cleaned.csv")
    communities = analyze_network(G)
    visualize_network(G, communities)
    
    # Find similar fragrances
    fragrance_name = "Sauvage Elixir"  # Example
    if fragrance_name in G:
        similar = []
        fragrance_notes = set(n for n in G.neighbors(fragrance_name) if G.nodes[n]['type'] == 'note')
        fragrance_accords = set(a for a in G.neighbors(fragrance_name) if G.nodes[a]['type'] == 'accord')
        
        for node in G.nodes():
            if G.nodes[node]['type'] == 'fragrance' and node != fragrance_name:
                node_notes = set(n for n in G.neighbors(node) if G.nodes[n]['type'] == 'note')
                node_accords = set(a for a in G.neighbors(node) if G.nodes[a]['type'] == 'accord')
                
                note_similarity = len(fragrance_notes & node_notes) / len(fragrance_notes | node_notes)
                accord_similarity = len(fragrance_accords & node_accords) / len(fragrance_accords | node_accords)
                
                similar.append((node, (note_similarity + accord_similarity) / 2))
        
        print(f"\nMost similar to {fragrance_name}:")
        for fragrance, similarity in sorted(similar, key=lambda x: x[1], reverse=True)[:5]:
            print(f"{fragrance}: {similarity:.2f} similarity")