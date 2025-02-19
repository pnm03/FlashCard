#include <iostream>

struct linkerList {
     linkerList *next = nullptr;
     int v;
};

linkerList* create_node () {
     linkerList *a = new linkerList;
     a->v = -1;
     a->next = nullptr;
     return a;
}

void add_head (linkerList *head, int value) {
     linkerList *a = new linkerList;
     a->v = value;
     if (head->next == nullptr) {
          head->next = a;
     }
     else {
          linkerList *b = new linkerList;
          b->next = head->next;

          head->next = a;
          a->next = b->next;
     }
}

void display (linkerList *head) {
     linkerList *a = new linkerList;
     a = head;
     if (a->next == nullptr) {
          std::cout << "danh sach rong\n";
          return;
     }
     else a = a->next;
     while (a->next != nullptr){
          std::cout << a->v << " ";
          a = a->next;
     }
     std::cout << a->v;
}

void add_end (linkerList *head, int value) {
     linkerList *a = new linkerList;
     a = head;
     if (a->next == nullptr) {
          add_head(head, value);
     }
     while (a->next != nullptr){
          a = a->next;
     }
     linkerList *b = new linkerList;
     b->v = value;
     a->next = b;
}


int main () {
     linkerList *head = create_node();
     add_head(head, 10);
     display(head);
     std::cout << "\n";
     add_head(head, 20);
     display(head);
     std::cout << "\n";
     add_head(head,30);
     display(head);
     std::cout << "\n";
     add_head(head,40);
     display(head);
     std::cout << "\n";
     add_end(head,50);
     display(head);



     return 0;
}