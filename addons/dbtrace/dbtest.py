print(">>> dbtest")
import DBListener

def callback(sql):
	print("callback2", sql)
	
def run(db):	
    print("m", callback.__module__)
    print("q", callback.__qualname__)
    DBListener.enable_trace(db, callback)
#    DBListener.enable_trace(db, callback)
#    DBListener.disable_trace(db, callback)

#    with DBListener.dbtracing(db, callback):
#        n = db.get_number_of_people()
#        print("n", n)
#    n = db.get_number_of_events()
#    print("n", n)
#    with DBListener.dbtracing(db, callback):
#        n = db.get_number_of_places()
#        print("n", n)
#
